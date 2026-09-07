"""New offline drafting jobs after human approval; never an agent tool.

Transaction A consumes approval and stores the running intent. Offline authoring
has no open database transaction. Transaction B atomically appends the terminal
job receipt and immutable pack. An interrupted RUNNING job is observable but is
never implicitly resumed; a receipt replay is not another authorization.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from pydantic import TypeAdapter

from qualor.domain.base import NonEmpty, UtcInstant
from qualor.eligibility.evidence import HARD_SOURCES
from qualor.eligibility.freshness import evaluate_freshness

from .approval import ApprovalDenied, ApprovalService
from .draft_templates import (
    DeterministicDraftAuthor,
    DraftAuthor,
    DraftInputSnapshot,
    DraftProse,
    assemble_sections,
    authoring_data,
)
from .models import (
    ApprovalBindings,
    ApprovalReason,
    DraftEvidenceVersion,
    DraftJobRecord,
    DraftPack,
)
from .store import WorkspaceStore

MAX_DRAFT_INPUT_BYTES = 128_000
_INSTANT = TypeAdapter(UtcInstant)
_TEXT = TypeAdapter(NonEmpty)


@dataclass(frozen=True)
class DraftJobResult:
    job: DraftJobRecord
    pack: DraftPack | None
    replayed: bool = False


class DraftingDenied(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _key(phase: str, operation_key: str) -> str:
    return hashlib.sha256(json.dumps(["DRAFT", phase, operation_key]).encode()).hexdigest()


class DraftingService:
    def __init__(self, approvals: ApprovalService, *, author: DraftAuthor | None = None):
        self.approvals = approvals
        self.database = approvals.database
        self.author = author if author is not None else DeterministicDraftAuthor()

    def _snapshot(self, store, approval, now) -> DraftInputSnapshot:
        opportunity = store.opportunities.get_opportunity_version(
            approval.opportunity_id, approval.opportunity_version
        )
        founder = store.profiles.get_founder(
            approval.founder_profile_id, approval.founder_profile_version
        )
        project = store.projects.get_project(approval.project_id, approval.project_version)
        decision = store.decisions.get_decision(approval.decision_id, approval.decision_version)
        if any(value is None for value in (opportunity, founder, project, decision)):
            raise DraftingDenied("SNAPSHOT_UNAVAILABLE")
        runs = tuple(
            run
            for run in store.runs.list_for_opportunity(opportunity.id, opportunity.version)
            if (run.decision_id, run.decision_version) == (decision.id, decision.version)
        )
        if len(runs) > 1:
            raise DraftingDenied("AMBIGUOUS_SOURCE_RUN")
        if not runs or runs[0].state != "COMPLETED" or runs[0].completed_at is None:
            raise DraftingDenied("SOURCE_RUN_NOT_COMPLETED")
        run = runs[0]
        if (
            run.mode != self.approvals.mode
            or run.completed_at > now
            or run.completed_at < max(run.created_at, decision.created_at)
            or (run.started_at is not None and run.completed_at < run.started_at)
        ):
            raise DraftingDenied("SOURCE_RUN_MISMATCH")
        refs = set(decision.conflict.evidence_ids)

        def collect(evaluation):
            refs.update(evaluation.evidence_ids)
            for child in evaluation.children:
                collect(child)

        for evaluation in decision.eligibility_gate.evaluations:
            collect(evaluation)
        decision_refs = tuple(sorted(refs))
        # Profile/project citations used in the authoring allowlist are proof
        # dependencies too, even when they are not critical decision evidence.
        # Resolving them changes provenance coverage, never eligibility or facts.
        proposed_facts, _ = authoring_data(founder, project, opportunity, (), decision)
        refs.update(ref for fact in proposed_facts for ref in fact.evidence_refs)
        evidence = []
        available = {
            e.id: e
            for e in store.evidence.list_for_opportunity(opportunity.id, opportunity.version)
        }
        for ref in sorted(refs):
            versions = store.evidence.list_versions(ref)
            if len(versions) > 1:
                raise DraftingDenied("AMBIGUOUS_EVIDENCE_REFERENCE")
            if len(versions) != 1 or ref not in available:
                raise DraftingDenied("EVIDENCE_REFERENCE_UNAVAILABLE")
            item = versions[0]
            if (
                item != available[ref]
                or item.extraction_state != "REVIEWED"
                or item.last_refresh_failed_at is not None
                or not (
                    item.source_type in HARD_SOURCES
                    or (
                        item.source_type == "SYNTHETIC_FIXTURE" and self.approvals.mode == "FIXTURE"
                    )
                )
                or evaluate_freshness(item.retrieved_at, now, min(opportunity.deadlines)) != "FRESH"
            ):
                raise DraftingDenied("EVIDENCE_NOT_ACTIONABLE")
            evidence.append(item)
        facts, missing = authoring_data(founder, project, opportunity, evidence, decision)
        records = (founder, project, opportunity, decision, runs[0], *evidence)
        if sum(len(r.model_dump_json().encode("utf-8")) for r in records) > MAX_DRAFT_INPUT_BYTES:
            raise DraftingDenied("DRAFT_INPUT_LIMIT")
        return DraftInputSnapshot(
            founder,
            project,
            opportunity,
            decision,
            tuple(evidence),
            runs[0],
            facts,
            missing,
            decision_refs,
            tuple(sorted(refs - set(decision_refs))),
        )

    @staticmethod
    def _existing(store, receipt, operation_key):
        refs = ((receipt.id, receipt.version),)
        jobs = store.drafts.list_jobs_for_approvals(refs)
        initial = [
            j for j in jobs if j.version == 1 and j.idempotency_key == _key("START", operation_key)
        ]
        if len(initial) != 1 or any(j.id != initial[0].id for j in jobs):
            raise DraftingDenied("CONSUMPTION_WITHOUT_JOB_INTENT")
        first = initial[0]
        if (
            len(jobs) not in {1, 2}
            or sorted(j.version for j in jobs) != list(range(1, len(jobs) + 1))
            or first.state != "RUNNING"
            or first.completed_at is not None
            or first.failure_reason is not None
            or first.source_run_id is None
            or first.source_run_version is None
        ):
            raise DraftingDenied("DRAFT_STATE_INCONSISTENT")
        latest = max(jobs, key=lambda j: j.version)
        immutable_fields = (
            "approval_id",
            "approval_version",
            "mode",
            "source_run_id",
            "source_run_version",
            "evidence_versions",
            "created_at",
            "started_at",
        )
        if any(getattr(latest, field) != getattr(first, field) for field in immutable_fields):
            raise DraftingDenied("DRAFT_STATE_INCONSISTENT")
        if latest.version == 2 and (
            latest.state not in {"COMPLETED", "FAILED"}
            or latest.idempotency_key != _key("OUTCOME", operation_key)
            or latest.completed_at is None
            or (latest.state == "FAILED") != (latest.failure_reason is not None)
        ):
            raise DraftingDenied("DRAFT_STATE_INCONSISTENT")
        packs = store.drafts.list_packs_for_approvals(refs)
        if len(packs) > 1 or (latest.state == "COMPLETED") != bool(packs):
            raise DraftingDenied("DRAFT_STATE_INCONSISTENT")
        pack = packs[0] if packs else None
        if pack is not None and (
            (pack.draft_job_id, pack.draft_job_version) != (latest.id, latest.version)
            or (pack.approval_id, pack.approval_version) != (receipt.id, receipt.version)
            or pack.evidence_versions != latest.evidence_versions
            or pack.evidence_refs != tuple(ref.evidence_id for ref in pack.evidence_versions)
            or pack.generated_at != latest.completed_at
        ):
            raise DraftingDenied("DRAFT_STATE_INCONSISTENT")
        return DraftJobResult(latest, pack, True)

    def start_draft_job(
        self, approval_id: str, idempotency_key: str, now: datetime
    ) -> DraftJobResult:
        instant = _INSTANT.validate_python(now)
        operation_key = _TEXT.validate_python(idempotency_key)
        with self.database.transaction(immediate=True) as connection:
            store = WorkspaceStore(connection)
            approved = store.approvals.latest(approval_id)
            if approved is None:
                raise ApprovalDenied(ApprovalReason.NOT_FOUND)
            bindings = ApprovalBindings.model_validate(
                {field: getattr(approved, field) for field in ApprovalBindings.model_fields}
            )
            try:
                receipt = self.approvals.consume_in_transaction(
                    store,
                    approval_id,
                    operation_key,
                    instant,
                    expected_versions=bindings,
                )
            except ApprovalDenied as exc:
                if exc.reason == ApprovalReason.EVIDENCE_CHANGED:
                    raise DraftingDenied("AMBIGUOUS_EVIDENCE_REFERENCE") from exc
                raise
            if receipt.replayed:
                return self._existing(store, receipt.record, operation_key)
            # Snapshot rejection rolls back consumption; replay never resolves new inputs.
            snapshot = self._snapshot(store, receipt.record, instant)
            job = DraftJobRecord(
                schema_version="1",
                id=str(uuid4()),
                version=1,
                created_at=instant,
                updated_at=instant,
                provenance="DOCUMENTED",
                approval_id=approval_id,
                approval_version=receipt.record.version,
                mode=self.approvals.mode,
                state="RUNNING",
                idempotency_key=_key("START", operation_key),
                started_at=instant,
                source_run_id=snapshot.source_run.id,
                source_run_version=snapshot.source_run.version,
                evidence_versions=tuple(
                    DraftEvidenceVersion(evidence_id=e.id, version=e.version)
                    for e in snapshot.evidence
                ),
            )
            store.drafts.put_draft_job(job)
        try:
            prose = DraftProse.model_validate(self.author.compose(snapshot))
            sections = assemble_sections(snapshot, prose)
        except Exception:
            return self._failed(job, operation_key, instant, "AUTHOR_FAILED")
        try:
            completed = self._terminal(job, operation_key, instant, "COMPLETED")
            pack = DraftPack(
                schema_version="1",
                id=str(uuid4()),
                version=1,
                created_at=instant,
                updated_at=instant,
                provenance="DOCUMENTED",
                **{
                    field: getattr(receipt.record, field)
                    for field in (
                        "opportunity_id",
                        "opportunity_hash",
                        "opportunity_version",
                        "founder_profile_id",
                        "founder_profile_version",
                        "project_id",
                        "project_version",
                        "decision_id",
                        "decision_version",
                        "policy_versions",
                    )
                },
                approval_id=approval_id,
                approval_version=receipt.record.version,
                draft_job_id=job.id,
                draft_job_version=completed.version,
                evidence_refs=tuple(e.id for e in snapshot.evidence),
                source_refs=tuple(sorted({e.source_id or e.final_url for e in snapshot.evidence})),
                missing_fields=snapshot.missing_fields,
                authoring_facts=snapshot.authoring_facts,
                sections=sections,
                generated_at=instant,
                creator_kind="DETERMINISTIC",
                evidence_versions=job.evidence_versions,
            )
            with self.database.transaction(immediate=True) as connection:
                store = WorkspaceStore(connection)
                store.drafts.put_draft_job(completed)
                store.drafts.put_draft_pack(pack)
            return DraftJobResult(completed, pack)
        except Exception:
            return self._failed(job, operation_key, instant, "PACK_PERSISTENCE_FAILED")

    @staticmethod
    def _terminal(job, key, now, state, reason=None):
        return DraftJobRecord.model_validate(
            {
                **job.model_dump(),
                "version": 2,
                "state": state,
                "updated_at": now,
                "completed_at": now,
                "failure_reason": reason,
                "idempotency_key": _key("OUTCOME", key),
            }
        )

    def _failed(self, job, key, now, reason):
        failed = self._terminal(job, key, now, "FAILED", reason)
        with self.database.transaction(immediate=True) as connection:
            WorkspaceStore(connection).drafts.put_draft_job(failed)
        return DraftJobResult(failed, None)
