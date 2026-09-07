"""Transaction-scoped facade over typed workspace repositories."""

import sqlite3
from dataclasses import dataclass

from qualor.decisions import DecisionRecord
from qualor.domain import EvidenceRecord, FounderProfile, OpportunityRecord, ProjectProfile
from qualor.persistence.repositories import (
    ApprovalRepository,
    DecisionRepository,
    DraftPackRepository,
    EvidenceRepository,
    OpportunityRepository,
    ProfileRepository,
    ProjectRepository,
    RunRepository,
)

from .models import ApprovalRecord, DraftJobRecord, DraftPack, RunEvent, RunRecord


@dataclass(frozen=True)
class DecisionSnapshot:
    decision: DecisionRecord
    founder_profile: FounderProfile
    project_profile: ProjectProfile


@dataclass(frozen=True)
class OpportunityWorkspace:
    opportunity: OpportunityRecord
    evidence: tuple[EvidenceRecord, ...]
    decisions: tuple[DecisionRecord, ...]
    runs: tuple[RunRecord, ...]
    decision_snapshots: tuple[DecisionSnapshot, ...]
    run_events: tuple[RunEvent, ...]


class WorkspaceStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.profiles = ProfileRepository(connection)
        self.projects = ProjectRepository(connection)
        self.opportunities = OpportunityRepository(connection)
        self.evidence = EvidenceRepository(connection)
        self.decisions = DecisionRepository(connection)
        self.runs = RunRepository(connection)
        self.approvals = ApprovalRepository(connection)
        self.drafts = DraftPackRepository(connection)

    def require_transaction(self) -> None:
        from qualor.persistence.repositories import TransactionRequiredError

        if not self.connection.in_transaction:
            raise TransactionRequiredError(
                "Approval consumption requires a caller-owned transaction"
            )

    def load_opportunity_workspace(
        self, opportunity_id: str, opportunity_version: int
    ) -> OpportunityWorkspace | None:
        opportunity = self.opportunities.get_opportunity_version(
            opportunity_id, opportunity_version
        )
        if opportunity is None:
            return None
        decisions = self.decisions.list_for_opportunity(opportunity_id, opportunity_version)
        snapshots = []
        for decision in decisions:
            founder_id = self.decisions.get_founder_profile_id(decision.id, decision.version)
            founder = (
                self.profiles.get_founder(founder_id, decision.profile_version)
                if founder_id is not None
                else None
            )
            project = self.projects.get_project(decision.project_id, decision.project_version)
            if founder is None or project is None:
                from qualor.persistence import InvalidReferenceError

                raise InvalidReferenceError("Decision snapshot reference is unavailable")
            snapshots.append(DecisionSnapshot(decision, founder, project))
        runs = self.runs.list_for_opportunity(opportunity_id, opportunity_version)
        return OpportunityWorkspace(
            opportunity=opportunity,
            evidence=self.evidence.list_for_opportunity(opportunity_id, opportunity_version),
            decisions=decisions,
            runs=runs,
            decision_snapshots=tuple(snapshots),
            run_events=tuple(event for run in runs for event in self.runs.list_run_events(run.id)),
        )

    def load_approval_graph(
        self, opportunity_id: str
    ) -> tuple[tuple[ApprovalRecord, ...], tuple[DraftJobRecord, ...], tuple[DraftPack, ...]]:
        approvals = self.approvals.list_for_opportunity(opportunity_id)
        references = tuple((record.id, record.version) for record in approvals)
        return (
            approvals,
            self.drafts.list_jobs_for_approvals(references),
            self.drafts.list_packs_for_approvals(references),
        )
