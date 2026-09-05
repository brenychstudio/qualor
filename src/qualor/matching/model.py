"""Immutable matching results with explicit input references."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, model_validator

from qualor.domain.base import Contract, NonEmpty, UtcInstant
from qualor.domain.planning import HourRange, MaterialKind

from .policy import FACTOR_COUNT, PARTIAL_THRESHOLD, STRONG_THRESHOLD, comparable_score

Rating = Annotated[StrictInt, Field(ge=0, le=4)]
Score = Annotated[StrictInt, Field(ge=0, le=100)]


class ReadinessState(StrEnum):
    READY = "READY"
    GAPS_EXECUTABLE = "GAPS_EXECUTABLE"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


class MatchStatus(StrEnum):
    STRONG = "STRONG"
    PARTIAL = "PARTIAL"
    WEAK = "WEAK"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class FactorResult(Contract):
    factor: NonEmpty
    rating: Rating | None
    reasons: tuple[NonEmpty, ...]
    requirement_refs: tuple[NonEmpty, ...]
    fact_refs: tuple[NonEmpty, ...]


class ReadinessAssessment(Contract):
    state: ReadinessState
    gaps: tuple[MaterialKind, ...]
    missing_information: tuple[NonEmpty, ...]
    factor_results: tuple[FactorResult, ...]
    evaluated_at: UtcInstant
    policy_version: Literal[1] = 1


class ProjectMatch(Contract):
    project_id: NonEmpty
    opportunity_id: NonEmpty
    factor_results: tuple[FactorResult, ...]
    missing_project_facts: tuple[NonEmpty, ...]
    matched_requirements: tuple[NonEmpty, ...]
    blocking_gaps: tuple[NonEmpty, ...]
    adaptation_hours: HourRange | None
    match_status: MatchStatus
    comparable_score: Score | None
    rating: Rating | None
    evaluated_at: UtcInstant
    policy_version: Literal[1] = 1

    @model_validator(mode="after")
    def consistent_score(self) -> Self:
        expected_factors = {
            "problem_audience",
            "technology",
            "features",
            "stage",
            "code_license",
            "adaptation",
            "readiness",
        }
        if (
            len(self.factor_results) != FACTOR_COUNT
            or {f.factor for f in self.factor_results} != expected_factors
        ):
            raise ValueError("Matching requires all seven distinct factors")
        ratings = tuple(f.rating for f in self.factor_results)
        score = None if None in ratings else comparable_score(ratings)
        rating = None if score is None else sum(ratings) // FACTOR_COUNT
        status = (
            MatchStatus.INSUFFICIENT_EVIDENCE
            if score is None
            else MatchStatus.STRONG
            if score >= STRONG_THRESHOLD
            else MatchStatus.PARTIAL
            if score >= PARTIAL_THRESHOLD
            else MatchStatus.WEAK
        )
        if (self.comparable_score, self.rating, self.match_status) != (score, rating, status):
            raise ValueError("Matching score, rating and status must follow factor evidence")
        return self


class ProjectSelection(Contract):
    best_project_id: NonEmpty | None
    candidates: Annotated[tuple[ProjectMatch, ...], Field(max_length=5)]
    reasons: tuple[NonEmpty, ...]

    @model_validator(mode="after")
    def valid_candidates(self) -> Self:
        ids = {m.project_id for m in self.candidates}
        if len(ids) != len(self.candidates):
            raise ValueError("Project IDs must be unique")
        if len({m.opportunity_id for m in self.candidates}) > 1:
            raise ValueError("Candidates must concern one opportunity")
        if self.best_project_id is not None and self.best_project_id not in ids:
            raise ValueError("Selected project must be a candidate")
        return self
