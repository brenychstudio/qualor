"""Transaction-scoped facade over typed workspace repositories."""

import sqlite3
from dataclasses import dataclass

from qualor.decisions import DecisionRecord
from qualor.domain import EvidenceRecord, OpportunityRecord
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

from .models import RunRecord


@dataclass(frozen=True)
class OpportunityWorkspace:
    opportunity: OpportunityRecord
    evidence: tuple[EvidenceRecord, ...]
    decisions: tuple[DecisionRecord, ...]
    runs: tuple[RunRecord, ...]


class WorkspaceStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.profiles = ProfileRepository(connection)
        self.projects = ProjectRepository(connection)
        self.opportunities = OpportunityRepository(connection)
        self.evidence = EvidenceRepository(connection)
        self.decisions = DecisionRepository(connection)
        self.runs = RunRepository(connection)
        self.approvals = ApprovalRepository(connection)
        self.drafts = DraftPackRepository(connection)

    def load_opportunity_workspace(
        self, opportunity_id: str, opportunity_version: int
    ) -> OpportunityWorkspace | None:
        opportunity = self.opportunities.get_opportunity_version(
            opportunity_id, opportunity_version
        )
        if opportunity is None:
            return None
        return OpportunityWorkspace(
            opportunity=opportunity,
            evidence=self.evidence.list_for_opportunity(opportunity_id, opportunity_version),
            decisions=self.decisions.list_for_opportunity(opportunity_id, opportunity_version),
            runs=self.runs.list_for_opportunity(opportunity_id, opportunity_version),
        )
