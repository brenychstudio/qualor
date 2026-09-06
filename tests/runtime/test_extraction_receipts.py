import json
from dataclasses import asdict
from decimal import Decimal

import pytest
from test_context_extraction import fetch_one, fetched_run
from test_extraction_wire import wire_claim_payload

from qualor.runtime.extraction import BedrockClaimExtractor


def response(text, stop="end_turn", **changes):
    result = {
        "stopReason": stop,
        "usage": {"inputTokens": 100, "outputTokens": 512, "totalTokens": 612},
        "metrics": {"latencyMs": 123},
        "output": {"message": {"content": [{"text": text}]}},
    }
    result.update(changes)
    return result


def adapter(payload):
    class RecordedClient:
        def converse(self, **request):
            return payload

    run = fetched_run()
    _, reference = fetch_one(run)
    source = run.sources[reference["source_id"]]
    return BedrockClaimExtractor(RecordedClient()), source


@pytest.mark.parametrize(
    ("stop", "code"),
    [
        ("max_tokens", "EXTRACTION_OUTPUT_TRUNCATED"),
        ("malformed_model_output", "BEDROCK_MALFORMED_MODEL_OUTPUT"),
        ("content_filtered", "BEDROCK_CONTENT_FILTERED"),
        ("guardrail_intervened", "BEDROCK_GUARDRAIL_INTERVENED"),
        ("model_context_window_exceeded", "BEDROCK_CONTEXT_WINDOW_EXCEEDED"),
    ],
)
def test_R01_R02_stop_semantics_precede_json_and_schema(stop, code):
    extractor, source = adapter(response('{"claims":[', stop))
    with pytest.raises(ValueError, match=f"^{code}$"):
        extractor.extract(source, "technology")
    receipt = extractor.receipts[-1]
    assert receipt.stop_reason == stop
    assert receipt.json_decode_state == "NOT_ATTEMPTED"
    assert receipt.schema_validation_state == "NOT_ATTEMPTED"


def test_R03_R06_R09_valid_receipt_is_safe_and_complete():
    extractor, source = adapter(response(""))

    def complete(**request):
        body = json.loads(request["messages"][0]["content"][0]["text"])
        text = json.dumps(
            {
                "claims": [
                    wire_claim_payload(
                        body["EVIDENCE_SPANS"][0]["span_id"], source_id=source.id
                    )
                ]
            }
        )
        return response(text)

    extractor.client.converse = complete
    claims = extractor.extract(source, "technology")
    receipt = asdict(extractor.receipts[-1])
    assert len(claims) == 1
    assert receipt["stop_reason"] == "end_turn"
    assert [receipt[k] for k in ("input_tokens", "output_tokens", "total_tokens")] == [
        100,
        512,
        612,
    ]
    assert receipt["content_block_count"] == 1
    assert receipt["content_block_types"] == ("text",)
    assert receipt["response_text_bytes"] > 0
    assert receipt["latency_ms"] == 123
    assert receipt["json_decode_state"] == receipt["schema_validation_state"] == "PASS"
    assert source.text not in json.dumps(receipt)
    assert source.final_url not in json.dumps(receipt)


@pytest.mark.parametrize(
    ("text", "code", "decode", "schema"),
    [
        ('{"claims":[', "JSON_DECODE_FAILED", "FAILED", "NOT_ATTEMPTED"),
        ('{"wrong":[]}', "EXTRACTION_SCHEMA_REJECTED", "PASS", "FAILED"),
    ],
)
def test_R04_R05_json_decode_and_schema_are_distinct(text, code, decode, schema):
    extractor, source = adapter(response(text))
    with pytest.raises(ValueError, match=f"^{code}$"):
        extractor.extract(source, "technology")
    assert extractor.receipts[-1].json_decode_state == decode
    assert extractor.receipts[-1].schema_validation_state == schema


def test_missing_or_hostile_envelope_is_not_assumed_complete_and_is_not_logged():
    extractor, source = adapter(response("SECRET_OUTPUT", "SECRET_STOP"))
    with pytest.raises(ValueError, match="BEDROCK_PROVIDER_ERROR"):
        extractor.extract(source, "technology")
    assert "SECRET" not in json.dumps(asdict(extractor.receipts[-1]))
    assert extractor.receipts[-1].stop_reason == "UNRECOGNIZED"


def test_provider_error_has_safe_receipt_without_exception_text():
    extractor, source = adapter(None)

    def failed(**kwargs):
        raise RuntimeError("credential=PRIVATE_MARKER")

    extractor.client.converse = failed
    with pytest.raises(ValueError, match="BEDROCK_PROVIDER_ERROR"):
        extractor.extract(source, "technology")
    assert "PRIVATE_MARKER" not in json.dumps(asdict(extractor.receipts[-1]))


def test_R13_independent_output_policies_and_shared_guard():
    from qualor.runtime.agent import BudgetedBedrockClient, live_extractor
    from qualor.runtime.budget import LiveBudgetGuard, LiveBudgetPolicy
    from qualor.runtime.extraction import build_extraction_request
    from qualor.runtime.model_policy import EXTRACTION_MAX_OUTPUT_TOKENS, STRANDS_MAX_OUTPUT_TOKENS

    assert STRANDS_MAX_OUTPUT_TOKENS == 512
    assert EXTRACTION_MAX_OUTPUT_TOKENS == 1024
    guard = LiveBudgetGuard(LiveBudgetPolicy(cost_cap_usd=Decimal(".20")))

    class Client:
        def converse(self, **request):
            return response('{"claims":[]}')

    client = BudgetedBedrockClient(Client(), guard)
    _, source = adapter(None)
    request = build_extraction_request(source, "technology", max_output_tokens=1024)
    client.converse(**request)
    assert guard.snapshot().inference_calls == 1
    with pytest.raises(ValueError, match="Bounded output"):
        client.converse(
            modelId=request["modelId"], messages=[], inferenceConfig={"maxTokens": 1024}
        )

    class Model:
        pass

    model = Model()
    model.client = client
    assert live_extractor(model).max_output_tokens == 1024


def test_R16_R18_receipt_survives_full_replay_and_critical_evidence_handoff():
    class RecordedExtraction:
        def __init__(self):
            self.receipts = []

        def extract(self, source, focus):
            outer = self

            class Client:
                def converse(self, **request):
                    assert request["inferenceConfig"]["maxTokens"] == 1024
                    body = json.loads(request["messages"][0]["content"][0]["text"])
                    return response(
                        json.dumps(
                            {
                                "claims": [
                                    wire_claim_payload(
                                        body["EVIDENCE_SPANS"][0]["span_id"],
                                        source_id=source.id,
                                    )
                                ]
                            }
                        )
                    )

            extractor = BedrockClaimExtractor(Client())
            claims = extractor.extract(source, focus)
            outer.receipts.extend(extractor.receipts)
            return claims

    run = fetched_run(extractor=RecordedExtraction())
    _, ref = fetch_one(run)
    result = run.extract_official_claims(ref["source_id"], "technology")
    assert result["status"] == "EXTRACTED"
    finished = run.finish()
    assert len(finished.claims) == 1
    assert finished.claims[0].evidence.id in finished.decision.model_dump_json()
    assert finished.decision.recommendation == "SKIP"
    assert run.extractor.receipts[0].stop_reason == "end_turn"
    assert run.budget.snapshot().inference_calls == run.budget.snapshot().search_calls == 0


def test_R10_R12_measured_two_claim_batch_fits_and_larger_batch_is_rejected():
    import runpy

    from pydantic import ValidationError

    from qualor.runtime.extraction import validate_extraction_payload

    report = runpy.run_path("scripts/extraction-budget-report.py")
    measurement = report["measure"]()
    assert measurement["estimated_output_tokens_by_claim_count"]["1"] > 0
    assert 512 < measurement["estimated_output_tokens_by_claim_count"]["2"] <= 1024
    assert len(validate_extraction_payload(report["owned_output"](2)).claims) == 2
    with pytest.raises(ValidationError):
        validate_extraction_payload(report["owned_output"](3))


def test_R14_R15_projected_total_is_bounded_and_real_overage_still_rejected():
    import runpy

    from qualor.runtime.budget import (
        BudgetLimitExceeded,
        LiveBudgetGuard,
        LiveBudgetPolicy,
        LiveCallKind,
    )

    report = runpy.run_path("scripts/extraction-budget-report.py")["measure"]()
    assert report["projected_total_run_cost_usd"] <= Decimal("0.20")
    assert report["projected_bedrock_calls"] == 5
    guard = LiveBudgetGuard(LiveBudgetPolicy(cost_cap_usd=Decimal("0.20")))
    receipt = guard.reserve(
        LiveCallKind.INFERENCE, estimated_cost_usd=report["projected_total_run_cost_usd"]
    )
    guard.commit(receipt)
    with pytest.raises(BudgetLimitExceeded):
        guard.reserve(LiveCallKind.INFERENCE, estimated_cost_usd=Decimal(".20"))


def test_stops_reach_tool_rejection_and_receipts_are_bounded():
    extractor, source = adapter(response('{"claims":[', "max_tokens"))
    run = fetched_run()
    _, ref = fetch_one(run)

    # Offline wrapper replays a recorded Converse envelope, never an AWS client.
    class Replay:
        receipts = extractor.receipts

        def extract(self, selected, focus):
            return extractor.extract(selected, focus)

    run.extractor = Replay()
    rejected = run.extract_official_claims(ref["source_id"], "technology")
    assert rejected["reason_code"] == "EXTRACTION_OUTPUT_TRUNCATED"
    assert not run.claims
    assert run.boundary_events[-1].reason_code == "EXTRACTION_OUTPUT_TRUNCATED"
    for _ in range(8):
        with pytest.raises(ValueError):
            extractor.extract(source, "technology")
    assert len(extractor.receipts) == 6
