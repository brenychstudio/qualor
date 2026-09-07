"""Transactional opportunity observation and restart reconstruction."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import TypeAdapter

from qualor.domain import FounderProfile, OpportunityRecord, ProjectProfile
from qualor.domain.base import UtcInstant
from qualor.domain.enums import FreshnessStatus
from qualor.eligibility.freshness import evaluate_freshness
from qualor.persistence import Database, InvalidReferenceError

from .models import ApprovalRecord, DraftJobRecord, DraftPack, RunEvent
from .store import DecisionSnapshot, OpportunityWorkspace, WorkspaceStore
from .versioning import (
    OPPORTUNITY_DIGEST_CRITICAL_FIELDS,
    opportunity_semantic_digest,
    opportunity_semantic_projection,
)

_INSTANT = TypeAdapter(UtcInstant)


def proof_freshness(item, opportunity, now, *, refresh_failed=False):
    if refresh_failed or item.last_refresh_failed_at is not None:
        return FreshnessStatus.STALE
    return evaluate_freshness(
        item.retrieved_at,
        now,
        opportunity.deadlines[0] if opportunity.deadlines else None,
        unknown_deadline=not opportunity.deadlines,
    )


def _workspace_freshness(statuses, failed):
    statuses = set(statuses)
    return (
        FreshnessStatus.STALE
        if failed or FreshnessStatus.STALE in statuses
        else FreshnessStatus.UNKNOWN
        if not statuses or FreshnessStatus.UNKNOWN in statuses
        else FreshnessStatus.FRESH
    )


class ApprovalVersionStatus(StrEnum):
    VERSION_MATCH_ONLY = "VERSION_MATCH_ONLY"
    VERSION_MISMATCH = "VERSION_MISMATCH"


class ObservationStatus(StrEnum):
    CHANGED = "CHANGED"
    UNCHANGED = "UNCHANGED"


class RefreshStatus(StrEnum):
    REFRESH_FAILED = "REFRESH_FAILED"


@dataclass(frozen=True)
class OpportunityVersionResult:
    opportunity_id: str
    version: int
    digest: str
    created: bool
    status: ObservationStatus
    changed_fields: tuple[str, ...]


@dataclass(frozen=True)
class RefreshFailureResult:
    opportunity_id: str
    opportunity_version: int
    failed_at: datetime
    status: RefreshStatus
    freshness: FreshnessStatus


@dataclass(frozen=True)
class ApprovalVersionAssessment:
    approval_id: str
    approval_version: int
    status: ApprovalVersionStatus


@dataclass(frozen=True)
class WorkspaceAggregate:
    current: OpportunityWorkspace
    history: tuple[OpportunityWorkspace, ...]
    freshness: FreshnessStatus
    last_refresh_failed_at: datetime | None
    approval_versions: tuple[ApprovalVersionAssessment, ...]
    founder_profiles: tuple[FounderProfile, ...]
    project_profiles: tuple[ProjectProfile, ...]
    approvals: tuple[ApprovalRecord, ...]
    draft_jobs: tuple[DraftJobRecord, ...]
    draft_packs: tuple[DraftPack, ...]
    run_events: tuple[RunEvent, ...]


@dataclass(frozen=True)
class CurrentProductWorkspace:
    current: OpportunityWorkspace
    freshness: FreshnessStatus
    last_refresh_failed_at: datetime | None
    selected_snapshot: DecisionSnapshot | None


class WorkspaceLifecycle:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _store(connection) -> WorkspaceStore:
        return WorkspaceStore(connection)

    def reconstruct_current_for_product(
        self, opportunity_id: str, now: datetime
    ) -> CurrentProductWorkspace:
        """Target the current decision graph; public history is separately paged.

        Freshness scans all current proof records with bounded memory. It never
        uses a public page as an input to authority or to freshness aggregation.
        """
        instant = _INSTANT.validate_python(now)
        with self.database.transaction() as connection:
            store = self._store(connection)
            latest = store.opportunities.latest_with_digest(opportunity_id)
            if latest is None:
                raise KeyError(opportunity_id)
            opportunity = latest[0]
            runs = store.runs.latest_for_opportunity(opportunity_id, opportunity.version)
            display_runs = runs
            if runs and all(run.decision_id is None for run in runs):
                display_runs = store.runs.latest_for_opportunity(
                    opportunity_id, opportunity.version, completed_decision=True
                )
            snapshots = []
            for run in display_runs:
                if run.decision_id is None:
                    continue
                decision = store.decisions.get_decision(run.decision_id, run.decision_version)
                if decision is None:
                    raise InvalidReferenceError("Decision snapshot reference is unavailable")
                founder_id = store.decisions.get_founder_profile_id(decision.id, decision.version)
                founder = store.profiles.get_founder(founder_id, decision.profile_version)
                project = store.projects.get_project(decision.project_id, decision.project_version)
                if founder is None or project is None:
                    raise InvalidReferenceError("Decision snapshot reference is unavailable")
                snapshots.append(DecisionSnapshot(decision, founder, project))
            failed = store.opportunities.latest_refresh_failure(opportunity_id, opportunity.version)
            statuses = set()
            for item in store.evidence.iter_for_opportunity(opportunity_id, opportunity.version):
                statuses.add(proof_freshness(item, opportunity, instant))
            freshness = _workspace_freshness(statuses, failed)
            current = OpportunityWorkspace(
                opportunity, (), tuple(s.decision for s in snapshots), runs, tuple(snapshots), ()
            )
            selected = snapshots[0] if len(snapshots) == 1 and len(display_runs) == 1 else None
            return CurrentProductWorkspace(current, freshness, failed, selected)

    def persist_observation(self, record: OpportunityRecord) -> OpportunityVersionResult:
        observed = OpportunityRecord.model_validate(record)
        digest = opportunity_semantic_digest(observed)
        with self.database.transaction(immediate=True) as connection:
            store = self._store(connection)
            latest = store.opportunities.latest_with_digest(observed.id)
            if latest is not None and latest[1] == digest:
                return OpportunityVersionResult(
                    observed.id,
                    latest[0].version,
                    digest,
                    False,
                    ObservationStatus.UNCHANGED,
                    (),
                )
            version = 1 if latest is None else latest[0].version + 1
            before = opportunity_semantic_projection(latest[0]) if latest else {}
            after = opportunity_semantic_projection(observed)
            changed_fields = tuple(
                field
                for field in OPPORTUNITY_DIGEST_CRITICAL_FIELDS
                if before.get(field) != after.get(field)
            )
            persisted = OpportunityRecord.model_validate(
                {**observed.model_dump(mode="json"), "version": version}
            )
            store.opportunities.put_opportunity_version(persisted, content_hash=digest)
            return OpportunityVersionResult(
                observed.id, version, digest, True, ObservationStatus.CHANGED, changed_fields
            )

    def mark_refresh_failed(
        self, opportunity_id: str, failed_at: datetime | str
    ) -> RefreshFailureResult:
        instant = _INSTANT.validate_python(failed_at)
        with self.database.transaction(immediate=True) as connection:
            store = self._store(connection)
            latest = store.opportunities.latest_with_digest(opportunity_id)
            if latest is None:
                raise KeyError(f"Unknown opportunity: {opportunity_id}")
            store.opportunities.record_refresh_failure(opportunity_id, latest[0].version, instant)
            return RefreshFailureResult(
                opportunity_id,
                latest[0].version,
                instant,
                RefreshStatus.REFRESH_FAILED,
                FreshnessStatus.STALE,
            )

    def reconstruct_workspace(self, opportunity_id: str, now: datetime | str) -> WorkspaceAggregate:
        _INSTANT.validate_python(now)
        with self.database.transaction() as connection:
            store = self._store(connection)
            versions = store.opportunities.list_versions(opportunity_id)
            if not versions:
                raise KeyError(f"Unknown opportunity: {opportunity_id}")
            history = tuple(
                workspace
                for record in versions
                if (workspace := store.load_opportunity_workspace(opportunity_id, record.version))
                is not None
            )
            current = history[-1]
            latest = store.opportunities.latest_with_digest(opportunity_id)
            if latest is None:  # protected by the non-empty versions check above
                raise RuntimeError("Opportunity version disappeared during reconstruction")
            current_digest = latest[1]
            failures = store.opportunities.list_refresh_failures(
                opportunity_id, current.opportunity.version
            )
            approvals, draft_jobs, draft_packs = store.load_approval_graph(opportunity_id)
            founders = {
                (
                    snapshot.founder_profile.id,
                    snapshot.founder_profile.version,
                ): snapshot.founder_profile
                for workspace in history
                for snapshot in workspace.decision_snapshots
            }
            projects = {
                (
                    snapshot.project_profile.id,
                    snapshot.project_profile.version,
                ): snapshot.project_profile
                for workspace in history
                for snapshot in workspace.decision_snapshots
            }
            for approval in approvals:
                founder = store.profiles.get_founder(
                    approval.founder_profile_id, approval.founder_profile_version
                )
                project = store.projects.get_project(approval.project_id, approval.project_version)
                decision = store.decisions.get_decision(
                    approval.decision_id, approval.decision_version
                )
                decision_founder_id = store.decisions.get_founder_profile_id(
                    approval.decision_id, approval.decision_version
                )
                if founder is None or project is None or decision is None:
                    raise InvalidReferenceError("Approval snapshot reference is unavailable")
                if (
                    decision.opportunity_id != approval.opportunity_id
                    or decision.opportunity_version != approval.opportunity_version
                    or decision.project_id != approval.project_id
                    or decision.project_version != approval.project_version
                    or decision_founder_id != approval.founder_profile_id
                    or decision.profile_version != approval.founder_profile_version
                ):
                    raise InvalidReferenceError("Approval decision snapshot links diverge")
                founders[(founder.id, founder.version)] = founder
                projects[(project.id, project.version)] = project
            assessments = tuple(
                ApprovalVersionAssessment(
                    approval.id,
                    approval.version,
                    ApprovalVersionStatus.VERSION_MATCH_ONLY
                    if (
                        approval.opportunity_version == current.opportunity.version
                        and approval.opportunity_hash == current_digest
                    )
                    else ApprovalVersionStatus.VERSION_MISMATCH,
                )
                for approval in approvals
            )
            evidence_freshness = (
                proof_freshness(item, current.opportunity, _INSTANT.validate_python(now))
                for item in current.evidence
            )
            freshness = _workspace_freshness(evidence_freshness, failures)
            return WorkspaceAggregate(
                current=current,
                history=history,
                freshness=freshness,
                last_refresh_failed_at=failures[-1] if failures else None,
                approval_versions=assessments,
                founder_profiles=tuple(founders.values()),
                project_profiles=tuple(projects.values()),
                approvals=approvals,
                draft_jobs=draft_jobs,
                draft_packs=draft_packs,
                run_events=tuple(event for item in history for event in item.run_events),
            )
