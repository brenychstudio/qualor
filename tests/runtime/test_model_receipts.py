"""Bounded model-call receipts expose accounting facts, never model content."""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError


def outcome(status, *, conditional=False, reasons=("SOURCE_EXPRESSION_SUPPORTED",), key="a"):
    return SimpleNamespace(
        normalization_status=status,
        conditional=conditional,
        reason_codes=reasons,
        model_dump=lambda **kwargs: {
            "category": "LICENSE",
            "normalization_status": status,
            "normalized_value": key,
            "rules": (),
            "evidence": (),
            "conditional": conditional,
            "reason_codes": reasons,
        },
    )


def test_lifecycle_assigns_call_index_only_at_dispatch_and_partitions_outcomes():
    from qualor.runtime.model_receipts import ReceiptLedger

    ledger = ReceiptLedger()
    slot = ledger.plan(
        "EXTRACTION",
        source_id="source_" + "a" * 32,
        section_id="section_" + "b" * 32,
        categories=("LICENSE", "REQUIRED_TECHNOLOGY"),
        authority_revision=3,
    )
    assert ledger.snapshot()[0].call_index is None
    ledger.dispatch(slot, reservation=Decimal("0.012"))
    assert ledger.snapshot()[0].execution_state == "DISPATCHED"
    ledger.complete(
        slot,
        outcomes=(
            outcome("SUPPORTED", conditional=True),
            outcome("SUPPORTED", conditional=True),
            outcome("AMBIGUOUS", reasons=("APPLICABILITY_UNRESOLVED",), key="b"),
        ),
        authority_revision=4,
        reconciled=Decimal("0.009"),
    )
    receipt = ledger.snapshot()[0]
    assert receipt.call_index == 1
    assert receipt.execution_state == "COMPLETED"
    assert (
        receipt.proposal_count,
        receipt.supported_count,
        receipt.conditional_count,
        receipt.ambiguous_count,
        receipt.unknown_count,
        receipt.unsupported_count,
        receipt.duplicate_count,
    ) == (3, 1, 1, 1, 0, 0, 1)
    assert receipt.rejection_codes == ("APPLICABILITY_UNRESOLVED", "DUPLICATE_PROPOSAL")
    assert receipt.authority_revision_before == 3
    assert receipt.authority_revision_after == 4


def test_budget_blocked_slot_is_not_a_paid_call():
    from qualor.runtime.model_receipts import ReceiptLedger

    ledger = ReceiptLedger()
    slot = ledger.plan("PLANNING")
    ledger.fail(slot, code="BUDGET_EXHAUSTED", budget_blocked=True)
    receipt = ledger.snapshot()[0]
    assert receipt.execution_state == "BUDGET_BLOCKED"
    assert receipt.call_index is None
    assert receipt.cost_reserved is None
    assert receipt.cost_reconciled is None


def test_post_dispatch_failure_remains_counted_and_cannot_be_rewritten():
    from qualor.runtime.model_receipts import ReceiptLedger

    ledger = ReceiptLedger()
    slot = ledger.plan("PLANNING", authority_revision=2)
    ledger.dispatch(slot, reservation=Decimal(".01"))
    ledger.fail(slot, code="MODEL_CALL_FAILED", budget_blocked=False)
    receipt = ledger.snapshot()[0]
    assert receipt.execution_state == "FAILED"
    assert receipt.call_index == 1
    assert receipt.cost_reserved == Decimal(".01")
    with pytest.raises(ValueError, match="terminal"):
        ledger.complete(slot, outcomes=(), authority_revision=2, reconciled=None)


def test_planning_client_orders_reservation_dispatch_physical_call_and_completion():
    from qualor.runtime.agent import BudgetedBedrockClient
    from qualor.runtime.budget import LiveBudgetGuard, LiveBudgetPolicy
    from qualor.runtime.extraction import MODEL_ID
    from qualor.runtime.model_receipts import ReceiptLedger

    ledger = ReceiptLedger()
    seen = []

    class Client:
        def converse(self, **request):
            seen.append(ledger.snapshot()[0].execution_state)
            return {"usage": {"inputTokens": 10, "outputTokens": 4}}

    guard = LiveBudgetGuard(
        LiveBudgetPolicy(cost_cap_usd=Decimal(".20"), authorization="QUALOR_03B3")
    )
    wrapped = BudgetedBedrockClient(Client(), guard)
    wrapped.bind_receipts(ledger, authority_revision=lambda: 7)
    wrapped.converse(
        modelId=MODEL_ID,
        messages=[],
        inferenceConfig={"maxTokens": 64},
    )
    receipt = ledger.snapshot()[0]
    assert seen == ["DISPATCHED"]
    assert receipt.execution_state == "COMPLETED"
    assert receipt.role == "PLANNING"
    assert receipt.authority_revision_before == receipt.authority_revision_after == 7
    assert receipt.cost_reconciled == Decimal(".00009")


def test_client_budget_denial_and_missing_usage_preserve_truth_without_raw_text():
    from qualor.runtime.agent import BudgetedBedrockClient
    from qualor.runtime.budget import BudgetLimitExceeded, LiveBudgetGuard, LiveBudgetPolicy
    from qualor.runtime.extraction import MODEL_ID
    from qualor.runtime.model_receipts import ReceiptLedger

    poison = "credential=PRIVATE_RECEIPT_SENTINEL"

    class NeverCalled:
        def converse(self, **request):
            raise AssertionError(poison)

    denied = ReceiptLedger()
    blocked = BudgetedBedrockClient(
        NeverCalled(),
        LiveBudgetGuard(
            LiveBudgetPolicy(cost_cap_usd=Decimal("0"), authorization="QUALOR_03B3")
        ),
    )
    blocked.bind_receipts(denied, authority_revision=lambda: 0)
    with pytest.raises(BudgetLimitExceeded):
        blocked.converse(
            modelId=MODEL_ID,
            messages=[],
            inferenceConfig={"maxTokens": 64},
        )
    denied_receipt = denied.snapshot()[0]
    assert denied_receipt.execution_state == "BUDGET_BLOCKED"
    assert denied_receipt.call_index is denied_receipt.cost_reconciled is None

    class MissingUsage:
        def converse(self, **request):
            return {"output": {"message": {"content": [{"text": poison}]}}}

    missing = ReceiptLedger()
    guard = LiveBudgetGuard(
        LiveBudgetPolicy(cost_cap_usd=Decimal(".20"), authorization="QUALOR_03B3")
    )
    wrapped = BudgetedBedrockClient(MissingUsage(), guard)
    wrapped.bind_receipts(missing, authority_revision=lambda: 0)
    with pytest.raises(RuntimeError, match="MODEL_USAGE_UNVERIFIED"):
        wrapped.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": poison}]}],
            inferenceConfig={"maxTokens": 64},
        )
    receipt = missing.snapshot()[0]
    assert receipt.execution_state == "FAILED"
    assert receipt.call_index == 1
    assert receipt.cost_reserved is not None
    assert receipt.cost_reconciled is None
    assert poison not in receipt.model_dump_json()
    assert guard.open_reservation_count == 1


@pytest.mark.parametrize("response", [{"usage": None}, []])
def test_every_malformed_planning_envelope_terminalizes_the_dispatched_receipt(response):
    from qualor.runtime.agent import BudgetedBedrockClient
    from qualor.runtime.budget import LiveBudgetGuard, LiveBudgetPolicy
    from qualor.runtime.extraction import MODEL_ID
    from qualor.runtime.model_receipts import ReceiptLedger

    class Malformed:
        def converse(self, **request):
            return response

    ledger = ReceiptLedger()
    wrapped = BudgetedBedrockClient(
        Malformed(),
        LiveBudgetGuard(
            LiveBudgetPolicy(cost_cap_usd=Decimal(".20"), authorization="QUALOR_03B3")
        ),
    )
    wrapped.bind_receipts(ledger, authority_revision=lambda: 0)
    with pytest.raises(RuntimeError, match="MODEL_USAGE_UNVERIFIED"):
        wrapped.converse(
            modelId=MODEL_ID,
            messages=[],
            inferenceConfig={"maxTokens": 64},
        )
    receipt = ledger.snapshot()[0]
    assert receipt.execution_state == "FAILED"
    assert receipt.call_index == 1
    assert receipt.cost_reserved is not None
    assert receipt.cost_reconciled is None
    assert receipt.rejection_codes == ("MODEL_USAGE_UNVERIFIED",)


def test_planned_and_dispatched_bounds_stop_before_losing_the_required_slot():
    from qualor.runtime.model_receipts import (
        MAX_DISPATCHED_MODEL_CALLS,
        MAX_PLANNED_SLOTS,
        ReceiptLedger,
    )

    ledger = ReceiptLedger()
    slots = [ledger.plan("PLANNING") for _ in range(MAX_PLANNED_SLOTS)]
    with pytest.raises(ValueError, match="MODEL_RECEIPT_PLAN_LIMIT"):
        ledger.plan("PLANNING")
    assert len(ledger.snapshot()) == MAX_PLANNED_SLOTS == 24
    for slot in slots[:MAX_DISPATCHED_MODEL_CALLS]:
        ledger.dispatch(slot, reservation=Decimal(".001"))
    with pytest.raises(ValueError, match="MODEL_RECEIPT_DISPATCH_LIMIT"):
        ledger.dispatch(slots[MAX_DISPATCHED_MODEL_CALLS], reservation=Decimal(".001"))
    assert ledger.snapshot()[MAX_DISPATCHED_MODEL_CALLS].execution_state == "PLANNED"
    assert sum(receipt.call_index is not None for receipt in ledger.snapshot()) == 9


def test_receipt_contract_rejects_extra_oversized_and_inconsistent_fields():
    from qualor.runtime.model_receipts import ModelCallReceipt

    valid = {
        "call_slot": 1,
        "call_index": None,
        "role": "PLANNING",
        "authority_revision_before": 0,
        "authority_revision_after": 0,
        "execution_state": "PLANNED",
    }
    with pytest.raises(ValidationError):
        ModelCallReceipt.model_validate({**valid, "prompt": "PRIVATE_PROMPT"})
    terminal_dispatched = {
        **valid,
        "call_index": 1,
        "cost_reserved": Decimal(".001"),
        "execution_state": "FAILED",
    }
    with pytest.raises(ValidationError) as oversized:
        ModelCallReceipt.model_validate(
            {**terminal_dispatched, "rejection_codes": ("X" * 81,)}
        )
    assert oversized.value.errors()[0]["loc"] == ("rejection_codes", 0)
    assert oversized.value.errors()[0]["type"] == "string_too_long"
    with pytest.raises(ValidationError):
        ModelCallReceipt.model_validate(
            {**valid, "call_index": 1, "execution_state": "BUDGET_BLOCKED"}
        )
    assert "PRIVATE" not in json.dumps(valid)


def test_opportunity_finish_counts_unique_retained_nonunsupported_section_candidates(
    grounded_candidate,
):
    from test_run_event_sink import build_run

    from qualor.runtime.adapters import adapt_candidate

    run = build_run()

    def adapted(category, value, quote, *, state="CANDIDATE"):
        candidate = grounded_candidate(category, value, quote, state=state)
        return adapt_candidate(candidate, evaluated_at=candidate.source.retrieved_at)

    supported = adapted("LICENSE", "MIT", "Projects must intend to use MIT licenses.")
    unknown = adapted(
        "REQUIRED_TECHNOLOGY",
        None,
        "The technology requirements remain to be clarified.",
        state="UNKNOWN",
    )
    unsupported = adapted("PROJECT_POLICY", "EXISTING_ALLOWED", "Projects may be existing.")
    run.section_results = (supported, supported, unknown, unsupported)
    result = run.finish()
    assert result.section_observation_count == 2
    assert result.claims == ()
