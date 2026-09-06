import json

import pytest
from pydantic import ValidationError


def claim_payload(**changes):
    value = {
        "source_id": "source_current",
        "source_url": "https://example.org/rules",
        "field": "required_technology",
        "value": ["Widget SDK"],
        "excerpt": "Projects must use Widget SDK.",
        "state": "CANDIDATE",
        "confidence": "HIGH",
    }
    value.update(changes)
    return value


def test_X01_X02_canonical_wrapped_json_array_validates_without_tuple_impedance():
    from qualor.runtime.extraction import validate_extraction_payload

    batch = validate_extraction_payload({"claims": [claim_payload()]})

    assert isinstance(batch.claims, tuple)
    assert batch.claims[0].value == ("Widget SDK",)


def test_X03_X04_missing_wrapper_and_bare_array_are_rejected():
    from qualor.runtime.extraction import validate_extraction_payload

    with pytest.raises(ValidationError) as missing:
        validate_extraction_payload(claim_payload())
    with pytest.raises(ValidationError) as bare:
        validate_extraction_payload([claim_payload()])

    assert missing.value.errors()[0]["type"] == "missing"
    assert bare.value.errors()[0]["type"] == "model_type"


def test_live_non_array_claims_error_class_is_reproduced_without_accepting_it():
    from qualor.runtime.extraction import ExtractedClaimBatch, validate_extraction_payload

    with pytest.raises(ValidationError) as live_shape:
        ExtractedClaimBatch.model_validate({"claims": claim_payload()})

    with pytest.raises(ValidationError) as invalid_collection:
        validate_extraction_payload({"claims": claim_payload()})

    assert live_shape.value.errors()[0]["loc"] == ("claims",)
    assert live_shape.value.errors()[0]["type"] == "tuple_type"
    assert invalid_collection.value.errors()[0]["loc"] == ("claims",)
    assert invalid_collection.value.errors()[0]["type"] in {"list_type", "value_error"}


def test_wire_contract_rejects_python_tuple_even_though_domain_uses_tuple():
    from qualor.runtime.extraction import validate_extraction_payload

    with pytest.raises(ValidationError):
        validate_extraction_payload({"claims": (claim_payload(),)})


def test_X05_X06_malformed_or_extra_claim_fields_are_rejected():
    from qualor.runtime.extraction import validate_extraction_payload

    with pytest.raises(ValidationError):
        validate_extraction_payload({"claims": [claim_payload(field="unsupported")]})
    with pytest.raises(ValidationError) as extra:
        validate_extraction_payload({"claims": [claim_payload(invented=True)]})

    assert extra.value.errors()[0]["type"] == "extra_forbidden"


def test_X07_empty_claim_batch_is_an_explicit_valid_no_findings_result():
    from qualor.runtime.extraction import validate_extraction_payload

    assert validate_extraction_payload({"claims": []}).claims == ()


def test_X08_unknown_claim_survives_wire_and_domain_validation():
    from qualor.runtime.extraction import validate_extraction_payload

    claim = claim_payload(value=None, state="UNKNOWN", confidence="UNKNOWN")

    batch = validate_extraction_payload({"claims": [claim]})

    assert batch.claims[0].state == "UNKNOWN"
    assert batch.claims[0].value is None


def test_X09_X10_wire_list_converts_to_immutable_domain_tuple():
    from qualor.runtime.extraction import ExtractedClaimBatchTransport

    transport = ExtractedClaimBatchTransport.model_validate({"claims": [claim_payload()]})
    transport.claims.append(transport.claims[0])
    domain = transport.to_domain()

    assert isinstance(transport.claims, list)
    assert isinstance(domain.claims, tuple)
    with pytest.raises(ValidationError):
        domain.claims = ()


def test_native_bedrock_json_schema_is_the_only_extraction_output_contract():
    from datetime import UTC, datetime

    from botocore.session import Session
    from botocore.validate import validate_parameters

    from qualor.runtime.extraction import build_extraction_request
    from qualor.runtime.sources import SourceDocument

    source = SourceDocument(
        id="source_current",
        original_url="https://example.org/rules",
        final_url="https://example.org/rules",
        retrieved_at=datetime.now(UTC),
        content_hash="a" * 64,
        authority="OFFICIAL_RULES",
        content_type="text/html",
        text="Projects must use Widget SDK.",
    )

    request = build_extraction_request(source, "required technology", max_output_tokens=512)
    definition = request["outputConfig"]["textFormat"]["structure"]["jsonSchema"]
    schema = json.loads(definition["schema"])

    assert "toolConfig" not in request
    assert request["outputConfig"]["textFormat"]["type"] == "json_schema"
    assert schema["type"] == "object"
    assert schema["required"] == ["claims"]
    assert schema["properties"]["claims"]["type"] == "array"
    operation = Session().get_service_model("bedrock-runtime").operation_model("Converse")
    validate_parameters(request, operation.input_shape)


def test_bedrock_schema_projection_contains_only_supported_json_schema_keywords():
    from datetime import UTC, datetime

    from qualor.runtime.extraction import build_extraction_request
    from qualor.runtime.sources import SourceDocument

    source = SourceDocument(
        id="source_current",
        original_url="https://example.org/rules",
        final_url="https://example.org/rules",
        retrieved_at=datetime.now(UTC),
        content_hash="a" * 64,
        authority="OFFICIAL_RULES",
        content_type="text/html",
        text="Projects must use Widget SDK.",
    )
    request = build_extraction_request(source, "required technology", max_output_tokens=512)
    schema = json.loads(
        request["outputConfig"]["textFormat"]["structure"]["jsonSchema"]["schema"]
    )
    forbidden = {
        "default",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "maxItems",
        "maxLength",
        "maximum",
        "minLength",
        "minimum",
        "multipleOf",
        "pattern",
    }

    def schema_keywords(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from schema_keywords(value)
        elif isinstance(node, list):
            for value in node:
                yield from schema_keywords(value)

    assert forbidden.isdisjoint(schema_keywords(schema))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["claims"]["type"] == "array"


def test_X11_X17_native_structured_text_reaches_existing_domain_claim_contract():
    from datetime import UTC, datetime

    from qualor.runtime.extraction import BedrockClaimExtractor
    from qualor.runtime.sources import SourceDocument

    source = SourceDocument(
        id="source_current",
        original_url="https://example.org/rules",
        final_url="https://example.org/rules",
        retrieved_at=datetime.now(UTC),
        content_hash="a" * 64,
        authority="OFFICIAL_RULES",
        content_type="text/html",
        text="Projects must use Widget SDK.",
    )

    class Client:
        def converse(self, **request):
            assert "outputConfig" in request
            return {
                "stopReason": "end_turn",
                "output": {
                    "message": {
                        "content": [{"text": json.dumps({"claims": [claim_payload()]})}]
                    }
                }
            }

    claims = BedrockClaimExtractor(Client()).extract(source, "required technology")

    assert isinstance(claims, tuple)
    assert claims[0].source_id == source.id
    assert claims[0].source_url == source.final_url
    assert claims[0].excerpt == "Projects must use Widget SDK."


def test_X11_X14_canonical_wire_replay_reaches_evidence_and_deterministic_decision():
    from test_context_extraction import fetch_one, fetched_run

    from qualor.runtime.extraction import BedrockClaimExtractor

    class RecordedNativeExtraction:
        def extract(self, source, focus):
            del focus

            class Client:
                def converse(self, **request):
                    assert "outputConfig" in request
                    payload = {
                        "claims": [
                            claim_payload(
                                source_id=source.id,
                                source_url=source.final_url,
                            )
                        ]
                    }
                    return {
                        "stopReason": "end_turn",
                        "output": {
                            "message": {"content": [{"text": json.dumps(payload)}]}
                        }
                    }

            return BedrockClaimExtractor(Client()).extract(source, "required technology")

    run = fetched_run(extractor=RecordedNativeExtraction())
    _, reference = fetch_one(run)

    extracted = run.extract_official_claims(reference["source_id"], "required technology")
    decision = run.evaluate_current_state()

    assert extracted["status"] == "EXTRACTED"
    assert len(run.claims) == 1
    evidence_id = extracted["observations"][0]["evidence_id"]
    assert evidence_id in run.decision.model_dump_json()
    assert decision["recommendation"] == "SKIP"


def test_native_schema_request_projection_stays_within_acceptance_cap():
    from decimal import Decimal

    from test_context_extraction import fetch_one, fetched_run

    from qualor.runtime.agent import estimate_model_reservation
    from qualor.runtime.extraction import build_extraction_request

    run = fetched_run(text="x" * 60_000)
    _, reference = fetch_one(run)
    request = build_extraction_request(
        run.sources[reference["source_id"]], "deadline", max_output_tokens=512
    )

    run_three_ledger = Decimal("0.077949")
    isolated_planning_reservation = Decimal("0.043560")
    projected_total = (
        run_three_ledger + isolated_planning_reservation + estimate_model_reservation(request)
    )

    assert projected_total <= Decimal("0.20")
