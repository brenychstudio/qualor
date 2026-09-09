"""Product composition over the persisted workspace and existing application authority."""

from datetime import UTC, date, datetime
from urllib.parse import urlsplit

from qualor.domain import FounderProfile, ProjectProfile
from qualor.persistence import Database

from .approval import ApprovalDenied, ApprovalService
from .drafting import DraftingService
from .lifecycle import WorkspaceLifecycle, proof_freshness
from .models import ApprovalBindings, ApprovalReason
from .read_models import (
    ActionCapability,
    ActivityResponse,
    ApprovalRequest,
    ApprovalView,
    ConstraintsConflictWhyView,
    DeadlineView,
    DecisionCanvasView,
    DraftJobView,
    DraftPackView,
    EligibilityWhyView,
    EvidenceClaimView,
    EvidenceProofView,
    EvidenceSheetView,
    InboxItem,
    InboxResponse,
    OpportunityWorkspaceResponse,
    PageInfo,
    PortfolioView,
    ProjectFitWhyView,
    ProjectSummary,
    RewardDeadlineWhyView,
    RunEventView,
    RunView,
    StrategyView,
    TechnicalProvenanceView,
)
from .store import WorkspaceStore


class ProductFailure(RuntimeError):
    def __init__(self, code: str, status: int = 409):
        self.code = code
        self.status = status
        super().__init__(code)


def project_fields(model, record):
    """Only named public fields cross the transport boundary."""
    return {field: getattr(record, field) for field in model.model_fields}


def request_view(record):
    return ApprovalRequest(
        **{
            field: getattr(record, field)
            for field in ApprovalRequest.model_fields
            if hasattr(record, field)
        }
    )


def page_info(total, limit, offset):
    return PageInfo(offset=offset, limit=limit, total=total, has_more=offset + limit < total)


class WorkspaceService:
    def __init__(
        self,
        database: Database,
        *,
        approvals: ApprovalService,
        clock=lambda: datetime.now(UTC),
        drafting: DraftingService | None = None,
    ):
        self.database = database
        self.approvals = approvals
        self.drafting = drafting or DraftingService(approvals)
        self.clock = clock
        self.lifecycle = WorkspaceLifecycle(database)

    def portfolio(self) -> PortfolioView:
        with self.database.transaction() as connection:
            store = WorkspaceStore(connection)
            founders = store.profiles.list_current()
            # V1 has one founder profile; actor identity is an independent control-plane binding.
            founder = founders[0] if len(founders) == 1 else None
            projects = store.projects.list_current()
        return PortfolioView(founder=founder, projects=projects)

    def _aggregate(self, opportunity_id, *, now=None):
        try:
            return self.lifecycle.reconstruct_current_for_product(
                opportunity_id, self.clock() if now is None else now
            )
        except KeyError:
            raise ProductFailure("NOT_FOUND", 404) from None

    @staticmethod
    def _selected(aggregate):
        if hasattr(aggregate, "selected_snapshot"):
            return aggregate.selected_snapshot
        # Selection was made by the decision pipeline and referenced by its run.
        # Per-project candidate records alone cannot establish the best project.
        runs = aggregate.current.runs
        if not runs:
            return None
        newest = max(run.created_at for run in runs)
        refs = {(r.decision_id, r.decision_version) for r in runs if r.created_at == newest}
        if len(refs) != 1:
            return None
        selected = refs.pop()
        return next(
            (
                s
                for s in aggregate.current.decision_snapshots
                if (s.decision.id, s.decision.version) == selected
            ),
            None,
        )

    def _bindings(self, opportunity_id, request):
        return ApprovalBindings(
            actor_id=self.approvals.actor_id, opportunity_id=opportunity_id, **request.model_dump()
        )

    def _canvas(self, aggregate, *, now=None):
        instant = self.clock() if now is None else now
        opportunity = aggregate.current.opportunity
        snapshot = self._selected(aggregate)
        decision = snapshot.decision if snapshot else None
        deadlines = opportunity.deadlines
        deadline = DeadlineView(
            values=deadlines,
            timezone_status=(
                "UNKNOWN"
                if not deadlines
                else "CALENDAR_DATE_ONLY"
                if any(type(d) is date for d in deadlines)
                else "UTC"
            ),
        )
        capability = ActionCapability(available=False, reason="DECISION_NOT_ACTIONABLE")
        if snapshot:
            with self.database.transaction() as connection:
                digest = WorkspaceStore(connection).opportunities.latest_with_digest(
                    opportunity.id
                )[1]
            request = ApprovalRequest(
                opportunity_version=opportunity.version,
                opportunity_hash=digest,
                founder_profile_id=snapshot.founder_profile.id,
                founder_profile_version=snapshot.founder_profile.version,
                project_id=decision.project_id,
                project_version=decision.project_version,
                decision_id=decision.id,
                decision_version=decision.version,
                policy_versions=decision.policy_versions,
            )
            binding = self._bindings(opportunity.id, request)
            try:
                authority = self.approvals.for_workspace_request(binding, instant)
                result = authority.inspect_request(binding, instant)
                capability = ActionCapability(
                    available=result.actionable, reason=result.reason, approval_request=request
                )
            except ApprovalDenied as exc:
                capability = ActionCapability(
                    available=False, reason=exc.reason, approval_request=request
                )
        return DecisionCanvasView(
            decision_id=decision.id if decision else None,
            decision_version=decision.version if decision else None,
            recommendation=decision.recommendation if decision else None,
            summary=decision.explanation if decision else None,
            reason_codes=decision.reason_codes if decision else (),
            strategy=StrategyView(
                state="AVAILABLE"
                if decision and decision.strategy_score is not None
                else "NOT_ENOUGH_EVIDENCE",
                score=decision.strategy_score if decision else None,
                breakdown=decision.strategy_breakdown if decision else (),
                missing_factors=decision.strategy.missing_strategy_factors if decision else (),
            ),
            best_project=ProjectSummary(**project_fields(ProjectSummary, snapshot.project_profile))
            if snapshot
            else None,
            eligibility=decision.eligibility_gate.state if decision else None,
            effort=decision.effort if decision else None,
            deadline=deadline,
            readiness=decision.readiness if decision else None,
            freshness=aggregate.freshness,
            primary_blocker=next(
                iter(decision.project_match.blocking_gaps or decision.missing_information), None
            )
            if decision
            else None,
            missing_information=decision.missing_information if decision else (),
            primary_action=capability,
        )

    def _attention_tier(self, canvas, run, opportunity_id, now):
        """Presentation consumes existing run/safety results; never edits a decision."""
        if run is None:
            return 5  # DISCOVERED
        if run.state in {"CREATED", "RUNNING"}:
            return 4  # VERIFYING
        if run.state != "COMPLETED" or canvas.recommendation is None:
            return 2  # NEEDS_REVIEW
        if canvas.recommendation in {"APPLY", "PREPARE"}:
            if canvas.primary_action.approval_request is None:
                return 2
            binding = self._bindings(opportunity_id, canvas.primary_action.approval_request)
            try:
                authority = self.approvals.for_workspace_request(binding, now)
                reason = authority.inspect_consequential_safety(binding, now)
            except ApprovalDenied as exc:
                reason = exc.reason
            if reason != "VALID":
                return 2
            return 0 if canvas.recommendation == "APPLY" else 1
        reason = canvas.primary_action.reason
        if reason not in {
            "VALID",
            "DECISION_NOT_ACTIONABLE",
            "DEADLINE_UNKNOWN",
            "DEADLINE_PASSED",
        }:
            return 2  # Existing evidence/graph/policy safety denial.
        return {"WATCH": 3, "SKIP": 6}[canvas.recommendation]

    @staticmethod
    def _deadline_priority(deadline, now):
        if deadline.timezone_status != "UTC" or not deadline.values:
            return 1, now  # UNKNOWN: no invented instant.
        earliest = min(deadline.values)
        if earliest <= now:
            return 2, now  # PAST: timestamps do not order this bucket.
        return 0, earliest

    def _inbox_priority(self, canvas, run, discovered_at, opportunity_id, now):
        score = canvas.strategy.score
        return (
            self._attention_tier(canvas, run, opportunity_id, now),
            *self._deadline_priority(canvas.deadline, now),
            score is None,
            -score if score is not None else 0,
            datetime.max.replace(tzinfo=UTC) - discovered_at,
            opportunity_id,
        )

    def inbox(self, *, limit=50, offset=0) -> InboxResponse:
        now = self.clock()
        with self.database.transaction() as connection:
            repository = WorkspaceStore(connection).opportunities
            discoveries = {
                record.id: min(
                    version.created_at for version in repository.list_versions(record.id)
                )
                for record in repository.list_current()
            }
        items = []
        for opportunity_id, discovered_at in discoveries.items():
            aggregate = self._aggregate(opportunity_id, now=now)
            opportunity = aggregate.current.opportunity
            canvas = self._canvas(aggregate, now=now)
            run = max(aggregate.current.runs, key=lambda r: (r.created_at, r.id), default=None)
            items.append(
                (
                    self._inbox_priority(canvas, run, discovered_at, opportunity_id, now),
                    InboxItem(
                        opportunity_id=opportunity.id,
                        priority_rank=0,
                        discovered_at=discovered_at,
                        version=opportunity.version,
                        program_name=opportunity.program_name,
                        organizer=opportunity.organizer,
                        edition=opportunity.edition,
                        recommendation=canvas.recommendation,
                        run_state=run.state if run else None,
                        mode=run.mode if run else None,
                        best_project=canvas.best_project,
                        deadline=canvas.deadline,
                        effort=canvas.effort,
                        readiness=canvas.readiness,
                        primary_blocker=canvas.primary_blocker,
                        freshness=aggregate.freshness,
                        human_action_available=canvas.primary_action.available,
                    ),
                )
            )
        items.sort(key=lambda entry: entry[0])
        ranked = tuple(
            item.model_copy(update={"priority_rank": rank}) for rank, (_, item) in enumerate(items)
        )
        return InboxResponse(
            items=ranked[offset : offset + limit],
            profile_present=self.portfolio().founder is not None,
            page=page_info(len(ranked), limit, offset),
        )

    def workspace(
        self, opportunity_id, *, limit=50, run_offset=0, approval_offset=0
    ) -> OpportunityWorkspaceResponse:
        aggregate = self._aggregate(opportunity_id)
        opportunity = aggregate.current.opportunity
        snapshot = self._selected(aggregate)
        with self.database.transaction() as connection:
            store = WorkspaceStore(connection)
            runs, runs_total = store.runs.page_current(
                limit, run_offset, opportunity_id=opportunity_id
            )
            approvals, approvals_total = store.approvals.page_for_opportunity(
                opportunity_id, self.approvals.actor_id, limit, approval_offset
            )
        return OpportunityWorkspaceResponse(
            opportunity_id=opportunity.id,
            version=opportunity.version,
            program_name=opportunity.program_name,
            organizer=opportunity.organizer,
            edition=opportunity.edition,
            decision=self._canvas(aggregate),
            freshness=aggregate.freshness,
            last_refresh_failed_at=aggregate.last_refresh_failed_at,
            rewards=opportunity.rewards,
            coverage=snapshot.decision.eligibility_gate.critical_coverage if snapshot else (),
            run_ids=tuple(run.id for run in runs),
            approvals=tuple(self.approval(approval.id) for approval in approvals),
            runs_page=page_info(runs_total, limit, run_offset),
            approvals_page=page_info(approvals_total, limit, approval_offset),
        )

    def evidence(
        self, opportunity_id, *, technical=False, limit=50, proof_offset=0, claim_offset=0
    ) -> EvidenceSheetView:
        aggregate = self._aggregate(opportunity_id)
        opportunity = aggregate.current.opportunity
        snapshot = self._selected(aggregate)
        decision = snapshot.decision if snapshot else None
        referenced = set()

        def collect_references(evaluation):
            referenced.update(evaluation.evidence_ids)
            for child in evaluation.children:
                collect_references(child)

        if decision:
            for evaluation in decision.eligibility_gate.evaluations:
                collect_references(evaluation)
        with self.database.transaction() as connection:
            store = WorkspaceStore(connection)
            evidence_records, proof_total = store.evidence.page_for_opportunity(
                opportunity_id, opportunity.version, limit, proof_offset
            )
            # Claim state is independent of which proof page is visible.
            stale_refs = set()
            for item in store.evidence.iter_for_opportunity(opportunity_id, opportunity.version):
                if (
                    item.id in referenced
                    and proof_freshness(
                        item,
                        opportunity,
                        self.clock(),
                        refresh_failed=aggregate.last_refresh_failed_at is not None,
                    )
                    == "STALE"
                ):
                    stale_refs.add(item.id)
        proofs = []
        for item in evidence_records:
            freshness = proof_freshness(
                item,
                opportunity,
                self.clock(),
                refresh_failed=aggregate.last_refresh_failed_at is not None,
            )
            proofs.append(
                EvidenceProofView(
                    evidence_id=item.id,
                    evidence_version=item.version,
                    category=item.normalized_field,
                    excerpt=item.supporting_excerpt,
                    url=item.final_url,
                    original_url=item.original_url,
                    domain=urlsplit(item.final_url).hostname,
                    source_type=item.source_type,
                    source_id=item.source_id,
                    source_version=item.content_hash,
                    retrieved_at=item.retrieved_at,
                    freshness=freshness,
                    technical_provenance=TechnicalProvenanceView(
                        source_id=item.source_id,
                        extraction_state=item.extraction_state,
                        policy_version=decision.eligibility_gate.policy_version
                        if decision
                        else None,
                    )
                    if technical
                    else None,
                )
            )
        claims = []

        def visit(evaluation):
            reasons = tuple(dict.fromkeys((evaluation.reason_code, *evaluation.reason_codes)))
            state = (
                "STALE"
                if "STALE_EVIDENCE" in reasons
                or bool(stale_refs.intersection(evaluation.evidence_ids))
                else "CONFLICT"
                if "CONFLICT" in reasons
                else evaluation.status
            )
            claims.append(
                EvidenceClaimView(
                    rule_id=evaluation.rule_id,
                    state=state,
                    reason_codes=reasons,
                    evidence_refs=evaluation.evidence_ids,
                )
            )
            for child in evaluation.children:
                visit(child)

        if decision:
            for evaluation in decision.eligibility_gate.evaluations:
                visit(evaluation)
        return EvidenceSheetView(
            opportunity_id=opportunity.id,
            opportunity_version=opportunity.version,
            freshness=aggregate.freshness,
            claims=tuple(claims[claim_offset : claim_offset + limit]),
            proofs=tuple(proofs),
            claims_page=page_info(len(claims), limit, claim_offset),
            proofs_page=page_info(proof_total, limit, proof_offset),
            coverage=decision.eligibility_gate.critical_coverage if decision else (),
            eligibility=EligibilityWhyView(
                state=decision.eligibility_gate.state if decision else None,
                evaluated_at=decision.eligibility_gate.evaluated_at if decision else None,
                policy_version=decision.eligibility_gate.policy_version if decision else None,
            ),
            project_fit=ProjectFitWhyView(
                project=ProjectSummary(**project_fields(ProjectSummary, snapshot.project_profile))
                if snapshot
                else None,
                match_status=decision.project_match.match_status if decision else None,
                factor_results=decision.project_match.factor_results if decision else (),
                matched_requirement_refs=decision.project_match.matched_requirements
                if decision
                else (),
                missing_facts=decision.project_match.missing_project_facts if decision else (),
                blocking_gaps=decision.project_match.blocking_gaps if decision else (),
                evaluated_at=decision.project_match.evaluated_at if decision else None,
                policy_version=decision.project_match.policy_version if decision else None,
            ),
            constraints_conflicts=ConstraintsConflictWhyView(
                status=decision.conflict.status if decision else None,
                checked_rule_categories=decision.conflict.checked_rule_categories
                if decision
                else (),
                missing_rule_categories=decision.conflict.missing_rule_categories
                if decision
                else (),
                evidence_refs=decision.conflict.evidence_ids if decision else (),
                reasons=decision.conflict.reasons if decision else (),
                founder_constraints=snapshot.founder_profile.constraints if snapshot else (),
                evaluated_at=decision.conflict.evaluated_at if decision else None,
                policy_version=decision.conflict.policy_version if decision else None,
            ),
            reward_deadline=RewardDeadlineWhyView(
                rewards=opportunity.rewards,
                deadline=self._canvas(aggregate).deadline,
                evidence_refs=tuple(
                    p.evidence_id for p in proofs if p.category in {"DEADLINE", "REWARD_CONDITIONS"}
                ),
            ),
        )

    def activity(self, run_id=None, *, limit=50, offset=0, event_offset=0) -> ActivityResponse:
        with self.database.transaction() as connection:
            store = WorkspaceStore(connection)
            if run_id:
                run = store.runs.current(run_id)
                runs = (run,) if run else ()
                runs_total = len(runs)
                run_offset = 0
                event_offset = offset
            else:
                runs, runs_total = store.runs.page_current(limit, offset)
                run_offset = offset
            if run_id and not runs:
                raise ProductFailure("NOT_FOUND", 404)
            events, events_total = store.runs.page_events(limit, event_offset, run_id=run_id)
        return ActivityResponse(
            runs=tuple(RunView(**project_fields(RunView, run)) for run in runs),
            events=tuple(
                RunEventView(
                    **{
                        field: getattr(e, field) if hasattr(e, field) else getattr(e.payload, field)
                        for field in RunEventView.model_fields
                    }
                )
                for e in events
            ),
            runs_page=page_info(runs_total, limit, run_offset),
            events_page=page_info(events_total, limit, event_offset),
        )

    def _owned_approval(self, approval_id):
        with self.database.transaction() as connection:
            record = WorkspaceStore(connection).approvals.latest(approval_id)
        if record is None or record.actor_id != self.approvals.actor_id:
            raise ProductFailure("NOT_FOUND", 404)
        return record

    def approval(self, approval_id, *, result=None) -> ApprovalView:
        record = self._owned_approval(approval_id)
        binding = self._bindings(record.opportunity_id, request_view(record))
        valid = self._receipt_authority(record).inspect_approval(approval_id, binding, self.clock())
        record = valid.record
        with self.database.transaction() as connection:
            stored_job, stored_pack = WorkspaceStore(connection).drafts.summary_for_approval(
                approval_id
            )
        job = result.job if result else stored_job
        pack = result.pack if result else stored_pack
        return ApprovalView(
            id=record.id,
            version=record.version,
            actor_id=record.actor_id,
            opportunity_id=record.opportunity_id,
            action=record.action,
            state="DRAFT_READY" if pack else record.state,
            expires_at=record.expires_at,
            actionable=valid.actionable,
            reason=valid.reason,
            approved_snapshot=request_view(record),
            draft_job=DraftJobView(**project_fields(DraftJobView, job)) if job else None,
            pack_id=pack.id if pack else None,
        )

    def request_approval(self, opportunity_id, request) -> ApprovalView:
        self._aggregate(opportunity_id)
        binding = self._bindings(opportunity_id, request)
        data = binding.model_dump()
        data["profile_version"] = data.pop("founder_profile_version")
        authority = self.approvals.for_workspace_request(binding, self.clock())
        record = authority.request_approval(**data, deadline=None, now=self.clock())
        return self.approval(record.id)

    def confirm_approval(self, approval_id, request) -> ApprovalView:
        record = self._owned_approval(approval_id)
        binding = self._bindings(record.opportunity_id, request.expected_versions)
        authority = self._receipt_authority(record)
        authority.confirm_approval(
            approval_id, request.idempotency_key, self.clock(), expected_versions=binding
        )
        result = DraftingService(authority, author=self.drafting.author).start_draft_job(
            approval_id, request.idempotency_key, self.clock()
        )
        return self.approval(approval_id, result=result)

    def _receipt_authority(self, record):
        # Historical receipt mode remains stable for replay even after graph changes.
        # New transitions still revalidate the exact current source run and versions.
        if record.mode is None:
            raise ApprovalDenied(ApprovalReason.MODE_MISMATCH)
        return ApprovalService(
            self.database,
            actor_id=self.approvals.actor_id,
            policy_versions=self.approvals.policy_versions,
            mode=record.mode,
            require_completed_run=True,
        )

    def draft_pack(self, pack_id) -> DraftPackView:
        with self.database.transaction() as connection:
            pack = WorkspaceStore(connection).drafts.get_draft_pack(pack_id, 1)
        if pack is None:
            raise ProductFailure("NOT_FOUND", 404)
        approval = self._owned_approval(pack.approval_id)
        return DraftPackView(
            **{
                field: getattr(pack, field)
                for field in DraftPackView.model_fields
                if field not in {"actor_id", "mode", "approved_snapshot", "content_kind"}
            },
            actor_id=approval.actor_id,
            mode=approval.mode,
            approved_snapshot=request_view(pack),
        )

    def update_profile(self, request) -> PortfolioView:
        self._update_portfolio_record(request.profile, request.expected_version, founder=True)
        return self.portfolio()

    def update_project(self, project_id, request) -> PortfolioView:
        if request.project.id != project_id:
            raise ProductFailure("NOT_FOUND", 404)
        self._update_portfolio_record(request.project, request.expected_version, founder=False)
        return self.portfolio()

    def _update_portfolio_record(self, incoming, expected, *, founder):
        # Optimistic version check and append share the write transaction. Canonical
        # record metadata belongs to the controller, never the HTTP request.
        with self.database.transaction(immediate=True) as connection:
            store = WorkspaceStore(connection)
            if founder:
                ids = tuple(f.id for f in store.profiles.list_current())
                if ids and ids != (incoming.id,):
                    raise ProductFailure("NOT_FOUND", 404)
            current = (
                store.profiles.latest_founder(incoming.id)
                if founder
                else store.projects.latest_project(incoming.id)
            )
            if (current.version if current else 0) != expected:
                raise ProductFailure("VERSION_MISMATCH")
            if not founder and current is None:
                count = len(store.projects.list_current())
                if count >= 5:
                    raise ProductFailure("PROJECT_LIMIT")
            now = self.clock()
            record_type = FounderProfile if founder else ProjectProfile
            record = record_type.model_validate(
                {
                    **incoming.model_dump(),
                    "version": expected + 1,
                    "created_at": current.created_at if current else now,
                    "updated_at": now,
                    "schema_version": "1",
                    "provenance": "USER_ASSERTED",
                }
            )
            if founder:
                store.profiles.put_founder(record)
            else:
                store.projects.put_project(record)
        # ApprovalService checks exact current profile/project versions at every
        # action boundary, including after restart; no approval state is edited here.
