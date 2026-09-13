import json
from decimal import Decimal

import pytest

from qualor.runtime.budget import (
    BudgetLimitExceeded,
    LiveBudgetGuard,
    LiveBudgetPolicy,
    LiveCallKind,
)


def test_explicit_b3_budget_allows_nine_calls_only_with_smaller_cost_ceiling():
    policy = LiveBudgetPolicy(
        inference_max_calls=9, cost_cap_usd=Decimal("0.20"), authorization="QUALOR_03B3"
    )
    g = LiveBudgetGuard(policy)
    for _ in range(9):
        g.reserve(LiveCallKind.INFERENCE)
    with pytest.raises(BudgetLimitExceeded):
        g.reserve(LiveCallKind.INFERENCE)
    with pytest.raises(ValueError):
        LiveBudgetGuard(
            LiveBudgetPolicy(
                inference_max_calls=9, cost_cap_usd=Decimal("0.21"), authorization="QUALOR_03B3"
            )
        )
    with pytest.raises(ValueError):
        LiveBudgetGuard(
            LiveBudgetPolicy(
                inference_max_calls=10,
                cost_cap_usd=Decimal("0.20"),
                authorization="QUALOR_03B3",
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


def test_U11_U13_completed_model_reservation_is_reconciled_and_not_retained():
    from qualor.runtime.agent import BudgetedBedrockClient

    class Client:
        def converse(self, **request):
            return {"usage": {"inputTokens": 10, "outputTokens": 5}}

    guard = LiveBudgetGuard(LiveBudgetPolicy(inference_max_calls=2))
    BudgetedBedrockClient(Client(), guard).converse(
        modelId="global.anthropic.claude-sonnet-4-6",
        messages=[],
        inferenceConfig={"maxTokens": 100},
    )

    assert guard.snapshot().reserved_cost_usd == Decimal("0.000105")
    assert guard.open_reservation_count == 0


def test_U12_completed_search_cost_is_committed_once_not_left_as_open_reservation():
    guard = LiveBudgetGuard()
    receipt = guard.reserve(LiveCallKind.SEARCH, estimated_cost_usd=Decimal("0.009"))
    guard.commit(receipt)

    assert guard.snapshot().reserved_cost_usd == Decimal("0.009")
    assert guard.open_reservation_count == 0
    with pytest.raises(ValueError):
        guard.commit(receipt)


def test_U14_U15_cost_rejection_exposes_exact_projection_without_mutating_ledger():
    guard = LiveBudgetGuard(LiveBudgetPolicy(cost_cap_usd=Decimal("0.15")))
    first = guard.reserve(LiveCallKind.SEARCH, estimated_cost_usd=Decimal("0.061356"))
    guard.commit(first)

    with pytest.raises(BudgetLimitExceeded) as caught:
        guard.reserve(LiveCallKind.INFERENCE, estimated_cost_usd=Decimal("0.09"))

    error = caught.value
    assert error.current_cost_usd == Decimal("0.061356")
    assert error.attempted_cost_usd == Decimal("0.09")
    assert error.remaining_cost_usd == Decimal("0.088644")
    assert error.projected_cost_usd == Decimal("0.151356")
    assert guard.snapshot().reserved_cost_usd == Decimal("0.061356")
    assert guard.snapshot().inference_calls == 0


def test_diagnostic_policy_reduces_output_reservation_without_raising_cost_cap():
    from qualor.runtime.agent import BudgetedBedrockClient
    from qualor.runtime.live_cli import diagnostic_policy

    policy = diagnostic_policy()
    assert policy.model_max_output_tokens == 512
    assert policy.cost_cap_usd == Decimal("0.15")
    with pytest.raises(ValueError, match="Bounded output"):
        BudgetedBedrockClient(object(), LiveBudgetGuard(policy)).converse(
            modelId="global.anthropic.claude-sonnet-4-6",
            messages=[],
            inferenceConfig={"maxTokens": 513},
        )


def test_model_reservation_formula_is_explicit_and_integer_safe():
    from qualor.runtime.agent import estimate_model_reservation

    request = {"messages": [], "inferenceConfig": {"maxTokens": 512}}
    serialized_bytes = len(json.dumps(request, ensure_ascii=False).encode("utf-8"))

    assert estimate_model_reservation(request) == (
        Decimal(serialized_bytes + 2048) * Decimal("0.000003")
        + Decimal(512) * Decimal("0.000015")
    )


def test_budget_projection_reaches_run_result_boundary_diagnostics():
    from strands.models.model import Model
    from test_autonomous_loop import make_run

    from qualor.runtime.agent import run_agent

    class BlockedModel(Model):
        def update_config(self, **kwargs):
            pass

        def get_config(self):
            return {}

        async def structured_output(self, *args, **kwargs):
            raise AssertionError
            yield

        async def stream(self, *args, **kwargs):
            raise BudgetLimitExceeded(
                "Development cost cap would be exceeded",
                current_cost_usd=Decimal("0.061356"),
                attempted_cost_usd=Decimal("0.09"),
                cost_cap_usd=Decimal("0.15"),
            )
            yield

    result, _metrics = run_agent(make_run(mode="REPLAY"), model=BlockedModel())
    event = next(e for e in result.boundary_events if e.reason_code == "BUDGET_EXHAUSTED")

    assert event.budget_current_cost_usd == "0.061356"
    assert event.budget_attempted_cost_usd == "0.09"
    assert event.budget_remaining_cost_usd == "0.088644"
    assert event.budget_projected_cost_usd == "0.151356"
