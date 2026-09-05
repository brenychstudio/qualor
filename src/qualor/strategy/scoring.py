"""Pure weighted priorities; these scores never claim likelihood of winning."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import TypeAdapter, model_validator

from qualor.domain.base import Contract, NonEmpty, UtcInstant
from qualor.domain.money import NonNegativeDecimal
from qualor.domain.opportunity import OpportunityRecord
from qualor.domain.profiles import FounderProfile
from qualor.effort import AffordabilityAssessment, CapacityAssessment
from qualor.matching.model import ProjectMatch, Rating, ReadinessAssessment, Score

from .policy import STRATEGY_POLICY_VERSION, WEIGHTS
from .rubric import _goal_coverage


class StrategyFactors(Contract):
    product_fit: Rating | None
    readiness: Rating | None
    time_feasibility: Rating | None
    strategic_value: Rating | None
    economic_affordability: Rating | None


class StrategyContribution(Contract):
    factor: NonEmpty
    weight: Score
    rating: Rating | None
    contribution: NonNegativeDecimal | None


class StrategyAssessment(Contract):
    score: Score | None
    breakdown: tuple[StrategyContribution, ...]
    missing_strategy_factors: tuple[NonEmpty, ...]
    semantics: Literal["PRIORITIZATION_NOT_WIN_PROBABILITY"] = "PRIORITIZATION_NOT_WIN_PROBABILITY"
    evaluated_at: UtcInstant
    policy_version: Literal[1] = 1

    @model_validator(mode="after")
    def consistent_score(self) -> Self:
        if tuple((i.factor, i.weight) for i in self.breakdown) != WEIGHTS:
            raise ValueError("Strategy requires the five versioned factors and weights in order")
        for item in self.breakdown:
            expected = (
                None if item.rating is None else Decimal(item.rating * item.weight) / Decimal(4)
            )
            if item.contribution != expected:
                raise ValueError(
                    "Strategy contributions must follow the stated ratings and weights"
                )
        missing = tuple(i.factor for i in self.breakdown if i.rating is None)
        score = None if missing else (sum(i.rating * i.weight for i in self.breakdown) + 2) // 4
        if (self.score, self.missing_strategy_factors) != (score, missing):
            raise ValueError("Strategy aggregate must follow known factors without imputation")
        return self


def score_strategy(factors: StrategyFactors, evaluated_at: datetime) -> StrategyAssessment:
    factors = StrategyFactors.model_validate(factors)
    evaluated_at = TypeAdapter(UtcInstant).validate_python(evaluated_at)
    breakdown = tuple(
        StrategyContribution(
            factor=name,
            weight=weight,
            rating=getattr(factors, name),
            contribution=None
            if getattr(factors, name) is None
            else Decimal(getattr(factors, name) * weight) / Decimal(4),
        )
        for name, weight in WEIGHTS
    )
    missing = tuple(i.factor for i in breakdown if i.rating is None)
    return StrategyAssessment(
        score=None if missing else (sum(i.rating * i.weight for i in breakdown) + 2) // 4,
        breakdown=breakdown,
        missing_strategy_factors=missing,
        evaluated_at=evaluated_at,
        policy_version=STRATEGY_POLICY_VERSION,
    )


def derive_strategy(
    founder: FounderProfile,
    opportunity: OpportunityRecord,
    match: ProjectMatch,
    readiness: ReadinessAssessment,
    capacity: CapacityAssessment,
    affordability: AffordabilityAssessment,
    evaluated_at: datetime,
) -> StrategyAssessment:
    founder = FounderProfile.model_validate(founder)
    opportunity = OpportunityRecord.model_validate(opportunity)
    match = ProjectMatch.model_validate(match)
    readiness = ReadinessAssessment.model_validate(readiness)
    capacity = CapacityAssessment.model_validate(capacity)
    affordability = AffordabilityAssessment.model_validate(affordability)
    return score_strategy(
        StrategyFactors(
            product_fit=match.rating,
            readiness={"READY": 4, "GAPS_EXECUTABLE": 3, "NOT_READY": 0, "UNKNOWN": None}[
                readiness.state
            ],
            time_feasibility={"SUFFICIENT": 4, "INSUFFICIENT": 0, "UNKNOWN": None}[capacity.state],
            strategic_value=_goal_coverage(
                founder.strategic_goals.value, opportunity.strategic_benefits.value
            ),
            economic_affordability={"SUFFICIENT": 4, "INSUFFICIENT": 0, "UNKNOWN": None}[
                affordability.state
            ],
        ),
        evaluated_at,
    )
