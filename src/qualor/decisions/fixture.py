"""Strict source-facts envelope; derived assessments are never fixture inputs."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from qualor.conflicts import ActiveSubmission, ConflictRule
from qualor.domain.base import Contract, UtcInstant
from qualor.domain.evidence import EvidenceRecord
from qualor.domain.opportunity import OpportunityRecord
from qualor.domain.profiles import FounderProfile, ProjectProfile
from qualor.domain.rules import RuleCandidate
from qualor.effort import EffortAssumptions, ParticipationCosts


class ProjectDecisionInput(Contract):
    project: ProjectProfile
    effort: EffortAssumptions


class DecisionInput(Contract):
    schema_version: Literal["1"]
    mode: Literal["FIXTURE", "REPLAY", "LIVE"]
    founder: FounderProfile
    opportunity: OpportunityRecord
    projects: Annotated[tuple[ProjectDecisionInput, ...], Field(min_length=1, max_length=5)]
    eligibility_rules: Annotated[tuple[RuleCandidate, ...], Field(max_length=100)]
    evidence: Annotated[tuple[EvidenceRecord, ...], Field(max_length=500)]
    conflict_rules: tuple[ConflictRule, ...]
    active_submissions: tuple[ActiveSubmission, ...]
    participation_costs: ParticipationCosts
    evaluated_at: UtcInstant

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        for ids in ([p.project.id for p in self.projects], [e.id for e in self.evidence]):
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate project or evidence IDs")
        return self


class DecisionFixture(DecisionInput):
    mode: Literal["FIXTURE"]


class WorkspaceSeedInput(DecisionInput):
    """The development seeding envelope: an owned scenario, or a captured real source.

    FIXTURE is a situation authored to be replayed at any clock. REPLAY is a record of a
    real source as it actually read at a real instant, so its instants are the source's own
    and the seeding path must not move them. LIVE is refused here: this envelope reads a
    local file, and a file cannot have been fetched by the run that is reading it.
    """

    mode: Literal["FIXTURE", "REPLAY"]
