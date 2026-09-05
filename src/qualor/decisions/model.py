"""Immutable decision records and explicit, nullable portfolio summaries."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from qualor.conflicts import ConflictAssessment, ConflictStatus
from qualor.domain.base import Contract, NonEmpty, PositiveInt, Record
from qualor.domain.enums import FreshnessStatus, GateState
from qualor.domain.rules import EligibilityGate
from qualor.effort import AffordabilityAssessment, CapacityAssessment, EffortEstimate
from qualor.matching import ProjectMatch, ProjectSelection, ReadinessAssessment
from qualor.matching.model import Score
from qualor.strategy import StrategyAssessment, StrategyContribution


class Recommendation(StrEnum):
    APPLY = "APPLY"
    PREPARE = "PREPARE"
    WATCH = "WATCH"
    SKIP = "SKIP"


class RecommendationResult(Contract):
    recommendation: Recommendation
    explanation: NonEmpty
    reason_codes: tuple[NonEmpty, ...]
    next_action: NonEmpty


class PolicyVersions(Contract):
    eligibility: PositiveInt
    matching: PositiveInt
    effort: PositiveInt
    conflicts: PositiveInt
    strategy: PositiveInt
    decisions: Literal[1]


class DecisionRecord(Record):
    opportunity_id: NonEmpty
    opportunity_version: PositiveInt
    project_id: NonEmpty
    project_version: PositiveInt
    profile_version: PositiveInt
    eligibility_gate: EligibilityGate
    conflict_status: ConflictStatus
    conflict: ConflictAssessment
    project_match: ProjectMatch
    strategy_score: Score | None
    strategy_breakdown: tuple[StrategyContribution, ...]
    strategy: StrategyAssessment
    readiness: ReadinessAssessment
    capacity: CapacityAssessment
    affordability: AffordabilityAssessment
    effort: EffortEstimate
    recommendation: Recommendation
    explanation: NonEmpty
    reason_codes: tuple[NonEmpty, ...]
    missing_information: tuple[NonEmpty, ...]
    next_action: NonEmpty
    freshness_status: FreshnessStatus
    policy_versions: PolicyVersions

    @model_validator(mode="after")
    def aligned_assessments(self) -> Self:
        if (self.strategy_score, self.strategy_breakdown, self.conflict_status) != (
            self.strategy.score,
            self.strategy.breakdown,
            self.conflict.status,
        ):
            raise ValueError("Decision summaries must match their full assessments")
        if (self.project_id, self.opportunity_id) != (
            self.project_match.project_id,
            self.project_match.opportunity_id,
        ):
            raise ValueError("Decision identity must match the assessed project and opportunity")
        return self


class DecisionResult(Contract):
    mode: Literal["FIXTURE"] = "FIXTURE"
    best_project_id: NonEmpty | None
    selection: ProjectSelection
    candidate_semantics: Literal["CONDITIONAL_PER_PROJECT"] = "CONDITIONAL_PER_PROJECT"
    candidates: tuple[DecisionRecord, ...]
    selected_decision: DecisionRecord | None
    recommendation: Recommendation
    explanation: NonEmpty
    reasons: tuple[NonEmpty, ...]
    missing_information: tuple[NonEmpty, ...]
    eligibility: GateState | None
    project_match: ProjectMatch | None
    strategy: StrategyAssessment | None
    effort: EffortEstimate | None
    conflict: ConflictAssessment | None
    readiness: ReadinessAssessment | None
    capacity: CapacityAssessment | None
    affordability: AffordabilityAssessment | None

    @model_validator(mode="after")
    def aligned_selection(self) -> Self:
        if self.best_project_id != self.selection.best_project_id:
            raise ValueError("Best project must follow matching selection")
        if tuple(d.project_match for d in self.candidates) != self.selection.candidates:
            raise ValueError("Conditional decisions must match all selection candidates")
        selected = next((d for d in self.candidates if d.project_id == self.best_project_id), None)
        if self.selected_decision != selected:
            raise ValueError("Selected summary must refer to the selected candidate")
        for field in (
            "project_match",
            "strategy",
            "effort",
            "conflict",
            "readiness",
            "capacity",
            "affordability",
        ):
            if getattr(self, field) != (getattr(selected, field) if selected else None):
                raise ValueError("Portfolio assessments must align with the selected candidate")
        if self.eligibility != (selected.eligibility_gate.state if selected else None):
            raise ValueError("Portfolio eligibility must align with the selected candidate")
        if selected and self.recommendation != selected.recommendation:
            raise ValueError("Selected recommendation must be retained")
        if not selected and self.recommendation not in (Recommendation.WATCH, Recommendation.SKIP):
            raise ValueError("Unresolved portfolios cannot be actionable")
        return self


# Both names identify the same structured result contract.
StructuredDecisionResult = DecisionResult
