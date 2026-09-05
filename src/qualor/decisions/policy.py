"""Owner-approved six-rule recommendation policy, in priority order."""

from pydantic import StrictBool, TypeAdapter

from qualor.conflicts import ConflictStatus
from qualor.domain.enums import GateState
from qualor.effort import AffordabilityState, CapacityState
from qualor.matching import ReadinessState
from qualor.matching.model import Score

from .model import Recommendation, RecommendationResult

DECISION_POLICY_VERSION = 1
APPLY_THRESHOLD = 75
PREPARE_THRESHOLD = 60
NEXT_ACTIONS = {
    Recommendation.APPLY: "prepare application package",
    Recommendation.PREPARE: "close listed readiness gaps",
    Recommendation.WATCH: "resolve listed unknowns",
    Recommendation.SKIP: "record reason without action",
}


EXPLANATIONS = {
    "POLICY_RULE_1": (
        "A closed or expired opportunity, failed eligibility, or explicit conflict blocks action."
    ),
    "POLICY_RULE_2": (
        "Eligibility, conflict coverage or a strategy factor needs review before action."
    ),
    "POLICY_RULE_3": (
        "Checked eligibility, capacity, costs and ready materials "
        "support preparing an application package."
    ),
    "POLICY_RULE_4": (
        "The project qualifies with sufficient capacity; "
        "close the listed executable readiness gaps."
    ),
    "POLICY_RULE_5": "Resolve the listed capacity, cost or readiness limitations before action.",
    "POLICY_RULE_6": "The supplied facts do not meet the policy thresholds for action.",
    "OPPORTUNITY_STATUS_OR_TIMING_UNKNOWN": (
        "Confirm the opportunity is open and its exact deadline before action."
    ),
}
PORTFOLIO_EXPLANATION = (
    "Matching does not identify a unique best project. "
    "Candidate decisions are conditional per-project analyses."
)


def outcome(recommendation: Recommendation, *codes: str) -> RecommendationResult:
    return RecommendationResult(
        recommendation=recommendation,
        reason_codes=codes,
        next_action=NEXT_ACTIONS[recommendation],
        explanation=EXPLANATIONS[codes[0]],
    )


def recommend(
    eligibility: GateState,
    conflict: ConflictStatus,
    score: int | None,
    readiness: ReadinessState,
    capacity: CapacityState,
    affordability: AffordabilityState,
    *,
    closed_or_expired: bool,
) -> RecommendationResult:
    eligibility = TypeAdapter(GateState).validate_python(eligibility)
    conflict = TypeAdapter(ConflictStatus).validate_python(conflict)
    score = TypeAdapter(Score | None).validate_python(score)
    readiness = TypeAdapter(ReadinessState).validate_python(readiness)
    capacity = TypeAdapter(CapacityState).validate_python(capacity)
    affordability = TypeAdapter(AffordabilityState).validate_python(affordability)
    closed_or_expired = TypeAdapter(StrictBool).validate_python(closed_or_expired)
    blockers = tuple(
        code
        for condition, code in (
            (closed_or_expired, "CLOSED_OR_EXPIRED"),
            (eligibility == GateState.FAIL, "ELIGIBILITY_FAIL"),
            (conflict == ConflictStatus.BLOCKED_BY_EXPLICIT_RULE, "EXPLICIT_CONFLICT"),
        )
        if condition
    )
    if blockers:
        return outcome(Recommendation.SKIP, "POLICY_RULE_1", *blockers)
    unknowns = tuple(
        code
        for condition, code in (
            (eligibility == GateState.REVIEW_REQUIRED, "ELIGIBILITY_REVIEW_REQUIRED"),
            (conflict == ConflictStatus.REVIEW_REQUIRED, "CONFLICT_REVIEW_REQUIRED"),
            (score is None, "STRATEGY_SCORE_UNKNOWN"),
        )
        if condition
    )
    if unknowns:
        return outcome(Recommendation.WATCH, "POLICY_RULE_2", *unknowns)
    if (
        eligibility == GateState.PASS
        and score >= APPLY_THRESHOLD
        and capacity == CapacityState.SUFFICIENT
        and affordability == AffordabilityState.SUFFICIENT
        and readiness == ReadinessState.READY
        and conflict == ConflictStatus.NO_CONFLICT_DETECTED_IN_CHECKED_RULES
    ):
        return outcome(Recommendation.APPLY, "POLICY_RULE_3", "ACTIONABLE_REQUIREMENTS_CONFIRMED")
    if (
        eligibility == GateState.PASS
        and score >= PREPARE_THRESHOLD
        and readiness == ReadinessState.GAPS_EXECUTABLE
        and capacity == CapacityState.SUFFICIENT
        and conflict == ConflictStatus.NO_CONFLICT_DETECTED_IN_CHECKED_RULES
    ):
        return outcome(Recommendation.PREPARE, "POLICY_RULE_4", "EXECUTABLE_READINESS_GAPS")
    if (
        eligibility == GateState.PASS
        and score >= PREPARE_THRESHOLD
        and (
            capacity != CapacityState.SUFFICIENT
            or affordability == AffordabilityState.UNKNOWN
            or readiness == ReadinessState.UNKNOWN
        )
    ):
        return outcome(
            Recommendation.WATCH, "POLICY_RULE_5", "CAPACITY_COST_OR_READINESS_UNRESOLVED"
        )
    return outcome(Recommendation.SKIP, "POLICY_RULE_6", "ACTION_THRESHOLDS_NOT_MET")
