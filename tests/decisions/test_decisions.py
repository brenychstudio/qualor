from itertools import product

import pytest

from qualor.conflicts import ConflictStatus
from qualor.domain.enums import GateState
from qualor.effort import AffordabilityState, CapacityState
from qualor.matching import ReadinessState


def call(**changes):
    from qualor.decisions import recommend

    args = dict(
        eligibility=GateState.PASS,
        conflict=ConflictStatus.NO_CONFLICT_DETECTED_IN_CHECKED_RULES,
        score=100,
        readiness=ReadinessState.READY,
        capacity=CapacityState.SUFFICIENT,
        affordability=AffordabilityState.SUFFICIENT,
        closed_or_expired=False,
    )
    args.update(changes)
    return recommend(**args)


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"eligibility": "FAIL"}, "SKIP"),
        ({"conflict": "BLOCKED_BY_EXPLICIT_RULE"}, "SKIP"),
        ({"eligibility": "REVIEW_REQUIRED"}, "WATCH"),
        ({"score": None}, "WATCH"),
        ({"score": 75}, "APPLY"),
        ({"score": 74}, "SKIP"),
        ({"score": 60, "readiness": "GAPS_EXECUTABLE"}, "PREPARE"),
        ({"score": 59}, "SKIP"),
        ({"score": 80, "capacity": "UNKNOWN"}, "WATCH"),
        ({"capacity": "INSUFFICIENT"}, "WATCH"),
        ({"affordability": "UNKNOWN"}, "WATCH"),
        ({"readiness": "UNKNOWN"}, "WATCH"),
        ({"closed_or_expired": True}, "SKIP"),
    ],
)
def test_b01_to_b13(changes, expected):
    assert call(**changes).recommendation == expected


def test_b39_priority_cross_product_zero_unsafe_apply():
    unsafe = 0
    for gate, conflict, score, ready, capacity, affordable, closed in product(
        GateState,
        ConflictStatus,
        [None, 59, 60, 74, 75, 100],
        ReadinessState,
        CapacityState,
        AffordabilityState,
        [False, True],
    ):
        result = call(
            eligibility=gate,
            conflict=conflict,
            score=score,
            readiness=ready,
            capacity=capacity,
            affordability=affordable,
            closed_or_expired=closed,
        )
        if closed or gate == "FAIL" or conflict == "BLOCKED_BY_EXPLICIT_RULE":
            assert result.recommendation == "SKIP"
        elif gate == "REVIEW_REQUIRED" or conflict == "REVIEW_REQUIRED" or score is None:
            assert result.recommendation == "WATCH"
        if result.recommendation == "APPLY":
            unsafe += not (
                gate == "PASS"
                and conflict == "NO_CONFLICT_DETECTED_IN_CHECKED_RULES"
                and score is not None
                and score >= 75
                and ready == "READY"
                and capacity == "SUFFICIENT"
                and affordable == "SUFFICIENT"
                and not closed
            )
    assert unsafe == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"score": True},
        {"score": 75.0},
        {"score": -1},
        {"score": 101},
        {"score": "75"},
        {"eligibility": "UNKNOWN"},
        {"conflict": "NO_CONFLICT"},
        {"readiness": "yes"},
        {"capacity": True},
        {"affordability": "yes"},
        {"closed_or_expired": 1},
    ],
)
def test_invalid_policy_inputs(changes):
    with pytest.raises(ValueError):
        call(**changes)


def test_rule_four_does_not_add_affordability_predicate():
    assert (
        call(score=60, readiness="GAPS_EXECUTABLE", affordability="UNKNOWN").recommendation
        == "PREPARE"
    )
