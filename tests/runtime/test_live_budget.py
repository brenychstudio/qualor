from decimal import Decimal

import pytest

from qualor.runtime.budget import (
    BudgetLimitExceeded,
    LiveBudgetGuard,
    LiveBudgetPolicy,
    LiveCallKind,
)


def test_explicit_b3_budget_allows_six_calls_only_with_smaller_cost_ceiling():
    policy = LiveBudgetPolicy(
        inference_max_calls=6, cost_cap_usd=Decimal("0.20"), authorization="QUALOR_03B3"
    )
    g = LiveBudgetGuard(policy)
    for _ in range(6):
        g.reserve(LiveCallKind.INFERENCE)
    with pytest.raises(BudgetLimitExceeded):
        g.reserve(LiveCallKind.INFERENCE)
    with pytest.raises(ValueError):
        LiveBudgetGuard(
            LiveBudgetPolicy(
                inference_max_calls=6, cost_cap_usd=Decimal("0.21"), authorization="QUALOR_03B3"
            )
        )


def test_reconciliation_releases_only_once_and_never_resets_call_count():
    g = LiveBudgetGuard()
    receipt = g.reserve(LiveCallKind.INFERENCE, estimated_cost_usd=Decimal("0.1"))
    g.reconcile(receipt, actual_cost_usd=Decimal("0.01"))
    assert g.snapshot().reserved_cost_usd == Decimal("0.01")
    assert g.snapshot().inference_calls == 1
    with pytest.raises(ValueError):
        g.reconcile(receipt, actual_cost_usd=Decimal("0"))
