"""Compiler receipt snapshots persist privately and preserve legacy telemetry."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from qualor.persistence import Database
from qualor.runtime.run_models import AgentRunResult, TraceEvent
from qualor.workspace import WorkspaceStore
from qualor.workspace.read_models import RunEventView
from qualor.workspace.run_capture import WorkspaceRunCapture


def completed_receipt(**changes):
    from qualor.runtime.model_receipts import ModelCallReceipt

    values = {
        "call_slot": 1,
        "call_index": 1,
        "role": "EXTRACTION",
        "source_id": "source_" + "a" * 32,
        "section_id": "section_" + "b" * 32,
        "requested_categories": ("LICENSE",),
        "proposal_count": 1,
        "supported_count": 1,
        "authority_revision_before": 0,
        "authority_revision_after": 1,
        "execution_state": "COMPLETED",
        "cost_reserved": Decimal(".01"),
        "cost_reconciled": Decimal(".009"),
    }
    values.update(changes)
    return ModelCallReceipt(**values)


def persisted_events(database, run_id="receipt-run"):
    with database.transaction() as connection:
        return WorkspaceStore(connection).runs.list_run_events(run_id)


def test_final_receipt_snapshot_survives_failed_run_reopen_and_is_under_4096_bytes(tmp_path):
    poison = "PRIVATE_SOURCE_PROFILE_PROMPT_EXCEPTION_SENTINEL"
    database = Database(tmp_path / "receipts.db")
    capture = WorkspaceRunCapture(database, run_id="receipt-run", mode="LIVE")
    receipt = completed_receipt(rejection_codes=("MODEL_CALL_FAILED",))
    capture.trace_event(
        TraceEvent(
            event="MODEL_CALL_RECEIPT",
            reason_code="FINAL_MODEL_CALL_RECEIPT",
            receipt=receipt,
        ),
        mode="LIVE",
    )
    capture.run_failed(termination_reason="MODEL_CALL_FAILED")

    reopened = Database(tmp_path / "receipts.db")
    event = persisted_events(reopened)[0]
    encoded = event.payload.model_dump_json()
    assert event.event_type == "MODEL_CALL_RECEIPT"
    assert event.payload.receipt == receipt
    assert len(encoded.encode("utf-8")) <= 4096
    assert poison not in encoded


def test_public_run_event_view_cannot_expose_private_receipt_payload():
    receipt = completed_receipt()
    assert "receipt" not in RunEventView.model_fields
    with pytest.raises(ValidationError):
        RunEventView.model_validate(
            {
                "run_id": "run",
                "sequence": 1,
                "event_type": "MODEL_CALL_RECEIPT",
                "mode": "LIVE",
                "occurred_at": datetime(2026, 9, 13, tzinfo=UTC),
                "reason_code": "FINAL_MODEL_CALL_RECEIPT",
                "phase": None,
                "count": 0,
                "source_ids": (),
                "evidence_ids": (),
                "estimated_cost_usd": None,
                "reported_cost_usd": None,
                "receipt": receipt,
            }
        )


def test_agent_result_bounds_receipts_and_section_observations():
    from test_run_capture import result

    base = result().model_dump()
    validated = AgentRunResult.model_validate(
        {**base, "model_receipts": (completed_receipt(),), "section_observation_count": 18}
    )
    assert len(validated.model_receipts) == 1
    assert validated.section_observation_count == 18
    with pytest.raises(ValidationError):
        AgentRunResult.model_validate({**base, "section_observation_count": 19})
    with pytest.raises(ValidationError):
        AgentRunResult.model_validate(
            {**base, "model_receipts": (completed_receipt(),) * 25}
        )


def test_workspace_legacy_count_adds_section_observations_but_offline_defaults_unchanged(tmp_path):
    from test_run_capture import result

    database = Database(tmp_path / "counts.db")
    capture = WorkspaceRunCapture(database, run_id="receipt-run", mode="FIXTURE")
    capture.run_finished(result().model_copy(update={"section_observation_count": 2}))
    with database.transaction() as connection:
        record = WorkspaceStore(connection).runs.current("receipt-run")
    assert record.verified_claim_count == 2

    replay = WorkspaceRunCapture(database, run_id="replay-run", mode="REPLAY")
    replay.run_finished(result(mode="REPLAY"))
    with database.transaction() as connection:
        replay_record = WorkspaceStore(connection).runs.current("replay-run")
    assert replay_record.verified_claim_count == 0


def test_receipt_event_contains_no_candidate_values_or_source_body():
    poison = "PRIVATE_CANDIDATE_OR_SOURCE_BODY"
    event = TraceEvent(
        event="MODEL_CALL_RECEIPT",
        reason_code="FINAL_MODEL_CALL_RECEIPT",
        receipt=completed_receipt(),
    )
    encoded = event.model_dump_json()
    assert poison not in encoded
    assert all(
        forbidden not in json.loads(encoded)["receipt"]
        for forbidden in ("candidate_value", "prompt", "response", "source_body", "profile")
    )


def test_evaluation_failure_flushes_real_model_receipt_before_failed_run_reopen(tmp_path):
    from test_run_event_sink import studio_input

    from qualor.runtime.agent import BudgetedBedrockClient
    from qualor.runtime.budget import LiveBudgetGuard, LiveBudgetPolicy
    from qualor.runtime.extraction import MODEL_ID, BedrockClaimExtractor
    from qualor.runtime.loop import OpportunityRun
    from qualor.runtime.search import AgentCoreSearchProvider
    from qualor.runtime.sources import OfficialSourceFetcher

    poison = "PRIVATE_REAL_FAILURE_AND_MODEL_OUTPUT_SENTINEL"
    inputs = studio_input()
    database = Database(tmp_path / "exceptional-receipts.db")
    capture = WorkspaceRunCapture(
        database, run_id="receipt-run", mode="LIVE", inputs=inputs
    )
    budget = LiveBudgetGuard(
        LiveBudgetPolicy(cost_cap_usd=Decimal(".20"), authorization="QUALOR_03B3")
    )

    class ModelOutput:
        def converse(self, **request):
            return {
                "usage": {"inputTokens": 10, "outputTokens": 4},
                "output": {"message": {"content": [{"text": poison}]}},
            }

    client = BudgetedBedrockClient(ModelOutput(), budget)
    run = OpportunityRun(
        inputs,
        mode="LIVE",
        search=AgentCoreSearchProvider(mode="LIVE", transport=object(), budget=budget),
        fetcher=OfficialSourceFetcher(
            mode="LIVE",
            allowed_hosts=inputs.allowed_hosts,
            budget=budget,
            resolver=lambda host: ("93.184.216.34",),
            request=lambda url, address: (200, {"content-type": "text/plain"}, b"unused"),
        ),
        extractor=BedrockClaimExtractor(client),
        budget=budget,
        sink=capture,
    )
    client.converse(
        modelId=MODEL_ID,
        messages=[],
        inferenceConfig={"maxTokens": 64},
    )

    def evaluation_failure():
        raise RuntimeError(poison)

    run.evaluate_current_state = evaluation_failure
    with pytest.raises(RuntimeError, match=poison):
        run.finish()
    capture.run_failed(termination_reason="INTERNAL_LIVE_RUN_FAILURE")
    capture.require_persisted()

    reopened = Database(tmp_path / "exceptional-receipts.db")
    event = persisted_events(reopened)[0]
    assert event.event_type == "MODEL_CALL_RECEIPT"
    assert event.payload.receipt.execution_state == "COMPLETED"
    assert event.payload.receipt.call_index == 1
    assert event.payload.receipt.cost_reconciled == Decimal(".00009")
    assert poison not in event.payload.model_dump_json()
