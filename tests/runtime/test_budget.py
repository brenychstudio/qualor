from decimal import Decimal

import pytest

from qualor.runtime import BudgetLimitExceeded, LiveBudgetGuard, LiveBudgetPolicy, LiveCallKind


@pytest.mark.parametrize(
    ("kind", "limit"),
    [
        (LiveCallKind.INFERENCE, 3),
        (LiveCallKind.SEARCH, 5),
        (LiveCallKind.FETCH, 10),
    ],
)
def test_C04_C05_C06_each_live_call_cap_is_enforced(kind, limit):
    guard = LiveBudgetGuard()
    for _ in range(limit):
        guard.reserve(kind)

    with pytest.raises(BudgetLimitExceeded, match=f"{kind.value} call cap"):
        guard.reserve(kind)

    assert guard.calls_used(kind) == limit


def test_C10_cost_guard_rejects_before_mutating_the_ledger():
    guard = LiveBudgetGuard()
    guard.reserve(LiveCallKind.INFERENCE, estimated_cost_usd=Decimal("2.00"))
    before = guard.snapshot()

    with pytest.raises(BudgetLimitExceeded, match="cost cap"):
        guard.reserve(LiveCallKind.SEARCH, estimated_cost_usd=Decimal("0.01"))

    assert guard.snapshot() == before


def test_retry_reservations_count_as_new_calls():
    guard = LiveBudgetGuard()
    for _ in range(3):
        guard.reserve(LiveCallKind.INFERENCE)
    with pytest.raises(BudgetLimitExceeded):
        guard.reserve(LiveCallKind.INFERENCE)


def test_cost_reservations_require_decimal_and_nonnegative_values():
    guard = LiveBudgetGuard()
    with pytest.raises(TypeError):
        guard.reserve(LiveCallKind.SEARCH, estimated_cost_usd=0.1)
    with pytest.raises(ValueError):
        guard.reserve(LiveCallKind.SEARCH, estimated_cost_usd=Decimal("-0.01"))


@pytest.mark.parametrize(
    "policy",
    [
        LiveBudgetPolicy(inference_max_calls=4),
        LiveBudgetPolicy(search_max_calls=6),
        LiveBudgetPolicy(fetch_max_documents=11),
        LiveBudgetPolicy(cost_cap_usd=Decimal("2.01")),
    ],
)
def test_development_policy_cannot_raise_hard_ceilings(policy):
    with pytest.raises(ValueError, match="hard ceiling"):
        LiveBudgetGuard(policy=policy)
