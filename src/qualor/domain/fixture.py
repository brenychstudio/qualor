"""Validated input context. This development envelope cannot claim LIVE mode."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import Contract, UtcInstant
from .evidence import EvidenceRecord
from .opportunity import OpportunityRecord
from .profiles import FounderProfile, ProjectProfile
from .rules import RuleCandidate


class EvaluationContext(Contract):
    founder: FounderProfile
    project: ProjectProfile
    opportunity: OpportunityRecord
    evidence: Annotated[tuple[EvidenceRecord, ...], Field(max_length=500)]
    evaluated_at: UtcInstant
    mode: Literal["FIXTURE"]

    @model_validator(mode="after")
    def unique_evidence(self) -> Self:
        ids = [item.id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate evidence IDs")
        return self


class FixtureInput(Contract):
    schema_version: Literal["1"]
    mode: Literal["FIXTURE"]
    context: EvaluationContext
    rules: Annotated[tuple[RuleCandidate, ...], Field(max_length=100)]
