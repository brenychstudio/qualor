"""Maps bounded runtime facts onto persisted run history.

The runtime owns what happened. This adapter only records it. It never recomputes a
decision, invents an event, or reports a state the runtime did not reach.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from qualor.domain import OpportunityRecord
from qualor.domain.opportunity import normalize_url
from qualor.persistence import Database, RepositoryConflictError
from qualor.runtime.run_models import AgentRunResult, StudioInput, TraceEvent

from .models import RunEventPayload, RunRecord, RunState
from .store import WorkspaceStore
from .versioning import opportunity_semantic_digest

# Canonical user-facing phases. A new public runtime event must be mapped here explicitly.
PHASES: dict[str, str | None] = {
    "SEARCH_REQUESTED": "DISCOVERING",
    "SEARCH_RESULTS_RECEIVED": "DISCOVERING",
    "CANDIDATE_SELECTED": "DISCOVERING",
    "SOURCE_SELECTED": "DISCOVERING",
    "SOURCE_FETCHED": "VERIFYING",
    "SOURCE_REFERENCE_CREATED": "VERIFYING",
    "EVIDENCE_SPANS_CREATED": "VERIFYING",
    "STRUCTURED_EXTRACTION": "VERIFYING",
    "SOURCE_SPAN_SELECTED": "VERIFYING",
    "CLAIM_EXTRACTED": "VERIFYING",
    "CLAIM_NORMALIZATION_RESULT": "VERIFYING",
    "EVIDENCE_RECORDED": "VERIFYING",
    "ELIGIBILITY_EVALUATED": "EVALUATING",
    "HUMAN_REVIEW_NEEDED": "EVALUATING",
    "DECISION_EVALUATED": "DECISION_UPDATED",
    "RUN_TERMINATED": None,
}

TERMINAL_STATES: dict[str, RunState] = {
    "SUFFICIENT_CRITICAL_EVIDENCE": RunState.COMPLETED,
    "HARD_FAIL_CONFIRMED": RunState.COMPLETED,
    "BUDGET_EXHAUSTED": RunState.BUDGET_STOPPED,
    "NO_PROGRESS": RunState.PARTIAL,
    "TOOL_FAILURE_BOUND_REACHED": RunState.PARTIAL,
    "MAX_STEPS": RunState.PARTIAL,
}


class RunEventSink(Protocol):
    """Runtime-neutral observer. The runtime depends on this shape, never on persistence."""

    def trace_event(self, event: TraceEvent, *, mode: str) -> None: ...

    def run_finished(self, result: AgentRunResult) -> None: ...

    def run_failed(self, *, termination_reason: str, provider_state: str | None = None) -> None: ...


class WorkspaceRunCapture:
    """Buffers bounded events and writes one immutable run record at its terminal state.

    Run rows are unique per run id and are never updated, so the record is written once,
    already carrying the state the runtime actually reached.
    """

    def __init__(
        self,
        database: Database,
        *,
        run_id: str,
        mode: str,
        clock=lambda: datetime.now(UTC),
        budget=None,
        opportunity_id: str | None = None,
        opportunity_version: int | None = None,
        inputs: StudioInput | None = None,
    ):
        self.database = database
        self.budget = budget
        self.run_id = run_id
        self.mode = str(mode)
        self.clock = clock
        self.opportunity_id = opportunity_id
        self.opportunity_version = opportunity_version
        self.inputs = StudioInput.model_validate(inputs) if inputs is not None else None
        self._events: list[tuple[str, RunEventPayload, datetime]] = []
        self._started_at: datetime | None = None
        self._persisted = False
        self._persistence_error: Exception | None = None
        self._resolved_opportunity: tuple[str, int, str] | None = None

    @property
    def persistence_error(self) -> Exception | None:
        return self._persistence_error

    def _retain_failure(self, error: Exception) -> None:
        if self._persistence_error is None:
            self._persistence_error = error

    def resolve_opportunity_version(self, record: OpportunityRecord) -> OpportunityRecord:
        """Resolve the semantic version before decision creation without writing it."""

        observed = OpportunityRecord.model_validate(record)
        digest = opportunity_semantic_digest(observed)
        try:
            with self.database.transaction() as connection:
                latest = WorkspaceStore(connection).opportunities.latest_with_digest(observed.id)
            if latest is not None and latest[1] == digest:
                resolved = latest[0]
            else:
                version = 1 if latest is None else latest[0].version + 1
                resolved = OpportunityRecord.model_validate(
                    {**observed.model_dump(mode="json"), "version": version}
                )
            authority = (resolved.id, resolved.version, digest)
            # Evaluations before finalization are provisional: newly admitted evidence
            # may legitimately refine identity or semantics. Only the last resolved
            # bundle is eligible for the atomic graph commit.
            self._resolved_opportunity = authority
            return resolved
        except Exception as exc:  # noqa: BLE001 - observer-owned failure is checked later
            self._retain_failure(exc)
            return observed

    def trace_event(self, event: TraceEvent, *, mode: str) -> None:
        if str(mode) != self.mode:
            raise ValueError("Run event mode does not match the captured run mode")
        occurred_at = self.clock()
        if self._started_at is None:
            self._started_at = occurred_at
        self._events.append((event.event, self._payload(event), occurred_at))

    @staticmethod
    def _payload(event: TraceEvent) -> RunEventPayload:
        """Only bounded, already-public runtime fields cross into persistence."""
        return RunEventPayload(
            reason_code=event.reason_code,
            phase=PHASES.get(event.event),
            source_ids=event.source_ids,
            evidence_ids=event.span_ids,
            count=event.count,
            normalized_field=event.normalized_field,
            normalization_status=event.normalization_status,
        )

    def run_finished(
        self,
        result: AgentRunResult,
        *,
        reserved_cost_usd: Decimal | None = None,
        reported_cost_usd: Decimal | None = None,
    ) -> None:
        if self._persisted:
            raise RuntimeError("This run is already persisted; run records are immutable")
        try:
            if self._persistence_error is not None:
                return
            self._commit(
                state=TERMINAL_STATES[result.termination_reason],
                termination_reason=result.termination_reason,
                search_calls=result.search_calls,
                fetched_documents=result.fetched_documents,
                official_source_count=result.official_source_count,
                verified_claim_count=len(result.claims),
                reserved_cost_usd=reserved_cost_usd,
                reported_cost_usd=reported_cost_usd,
                result=result,
            )
        except Exception as exc:  # noqa: BLE001 - observer-owned failure is checked later
            self._retain_failure(exc)

    def run_failed(
        self,
        *,
        termination_reason: str,
        provider_state: str | None = None,
        state: RunState = RunState.FAILED,
    ) -> None:
        if self._persisted:
            raise RuntimeError("This run is already persisted; run records are immutable")
        try:
            if self._persistence_error is not None:
                return
            self._commit(
                state=state, termination_reason=termination_reason, provider_state=provider_state
            )
        except Exception as exc:  # noqa: BLE001 - observer-owned failure is checked later
            self._retain_failure(exc)

    def require_persisted(self) -> None:
        """Fail the explicit operator boundary when its requested capture did not commit."""

        if self._persistence_error is not None:
            raise RuntimeError("workspace persistence failed") from self._persistence_error
        if not self._persisted:
            raise RuntimeError("workspace persistence did not complete")

    def _commit(
        self,
        *,
        state: RunState,
        termination_reason: str,
        provider_state: str | None = None,
        search_calls: int = 0,
        fetched_documents: int = 0,
        official_source_count: int = 0,
        verified_claim_count: int = 0,
        reserved_cost_usd: Decimal | None = None,
        reported_cost_usd: Decimal | None = None,
        result: AgentRunResult | None = None,
    ) -> None:
        if self._persisted:
            raise RuntimeError("This run is already persisted; run records are immutable")
        if reserved_cost_usd is None and self.budget is not None:
            reserved_cost_usd = self.budget.snapshot().reserved_cost_usd
        completed_at = self.clock()
        started_at = self._started_at or completed_at
        graph = None
        if state == RunState.COMPLETED and result is not None and self.inputs is not None:
            graph = self._validated_graph(result)
        opportunity_id = graph.opportunity.id if graph is not None else self.opportunity_id
        opportunity_version = (
            graph.opportunity.version if graph is not None else self.opportunity_version
        )
        selected = graph.decision.selected_decision if graph is not None else None
        record = RunRecord(
            schema_version="1",
            id=self.run_id,
            version=1,
            created_at=started_at,
            updated_at=completed_at,
            provenance="DOCUMENTED",
            mode=self.mode,
            state=state,
            provider_state=provider_state,
            opportunity_id=opportunity_id,
            opportunity_version=opportunity_version,
            decision_id=selected.id if selected is not None else None,
            decision_version=selected.version if selected is not None else None,
            search_calls=search_calls,
            fetched_documents=fetched_documents,
            official_source_count=official_source_count,
            verified_claim_count=verified_claim_count,
            reserved_cost_usd=reserved_cost_usd or Decimal(0),
            reported_cost_usd=reported_cost_usd or Decimal(0),
            termination_reason=termination_reason,
            started_at=started_at,
            completed_at=completed_at,
        )
        with self.database.transaction() as connection:
            store = WorkspaceStore(connection)
            if graph is not None:
                self._persist_graph(store, graph)
            store.runs.create_run(record)
            for event_type, payload, occurred_at in self._events:
                store.runs.append_run_event(
                    self.run_id,
                    event_type=event_type,
                    payload=payload,
                    mode=self.mode,
                    occurred_at=occurred_at,
                )
        self._persisted = True

    def _validated_graph(self, result: AgentRunResult):
        graph = result.bundle
        if graph is None or graph.decision.selected_decision is None:
            raise ValueError("Completed LIVE workspace capture requires a selected graph")
        if result.mode != self.mode or graph.decision != result.decision:
            raise ValueError("Runtime result and persisted graph diverge")
        if (
            graph.decision_input.founder != self.inputs.founder
            or graph.decision_input.projects != self.inputs.projects
        ):
            raise ValueError("Runtime graph profile or projects diverge")
        if any(
            (decision.opportunity_id, decision.opportunity_version)
            != (graph.opportunity.id, graph.opportunity.version)
            for decision in graph.decision.candidates
        ):
            raise ValueError("Runtime decision references diverge from opportunity")
        authority = (
            graph.opportunity.id,
            graph.opportunity.version,
            opportunity_semantic_digest(graph.opportunity),
        )
        if self._resolved_opportunity not in (None, authority):
            raise ValueError("Runtime graph is not the final resolved opportunity authority")
        official_rules_urls = {
            normalize_url(item.final_url)
            for item in graph.evidence
            if item.source_type == "OFFICIAL_RULES"
        }
        if graph.opportunity.canonical_rules_url not in official_rules_urls:
            raise ValueError("Completed LIVE graph requires admitted official rules evidence")
        return graph

    @staticmethod
    def _put_immutable(current, record, put, name: str) -> None:
        existing = current(record.id, record.version)
        if existing is None:
            put(record)
        elif existing != record:
            raise RepositoryConflictError(f"Conflicting immutable {name} record")

    def _persist_graph(self, store: WorkspaceStore, graph) -> None:
        self._put_immutable(
            store.profiles.get_founder,
            self.inputs.founder,
            store.profiles.put_founder,
            "founder profile",
        )
        for item in self.inputs.projects:
            self._put_immutable(
                store.projects.get_project,
                item.project,
                store.projects.put_project,
                "project profile",
            )

        digest = opportunity_semantic_digest(graph.opportunity)
        latest = store.opportunities.latest_with_digest(graph.opportunity.id)
        if latest is None:
            if graph.opportunity.version != 1:
                raise RepositoryConflictError("Resolved opportunity version is no longer current")
            store.opportunities.put_opportunity_version(graph.opportunity, content_hash=digest)
        elif latest[1] == digest:
            if latest[0] != graph.opportunity:
                raise RepositoryConflictError("Resolved opportunity snapshot diverges")
        elif graph.opportunity.version == latest[0].version + 1:
            store.opportunities.put_opportunity_version(graph.opportunity, content_hash=digest)
        else:
            raise RepositoryConflictError("Resolved opportunity version is no longer current")

        scoped_evidence = {
            (item.id, item.version): item
            for item in store.evidence.list_for_opportunity(
                graph.opportunity.id, graph.opportunity.version
            )
        }
        for evidence in graph.evidence:
            key = (evidence.id, evidence.version)
            existing = store.evidence.get_evidence(evidence.id, evidence.version)
            if existing is None:
                store.evidence.put_evidence(
                    evidence, graph.opportunity.id, graph.opportunity.version
                )
                scoped_evidence[key] = evidence
            elif existing != evidence or scoped_evidence.get(key) != evidence:
                raise RepositoryConflictError("Conflicting immutable evidence record")
        for decision in graph.decision.candidates:
            existing = store.decisions.get_decision(decision.id, decision.version)
            if existing is None:
                store.decisions.put_decision(
                    decision, founder_profile_id=self.inputs.founder.id
                )
            elif (
                existing != decision
                or store.decisions.get_founder_profile_id(decision.id, decision.version)
                != self.inputs.founder.id
            ):
                raise RepositoryConflictError("Conflicting immutable decision record")
