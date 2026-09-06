import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from qualor.runtime.sources import SourceDocument


def source(*, source_id="source_current"):
    return SourceDocument(
        id=source_id,
        original_url="https://example.org/rules",
        final_url="https://example.org/rules",
        retrieved_at=datetime(2026, 9, 6, tzinfo=UTC),
        content_hash="a" * 64,
        authority="OFFICIAL_RULES",
        content_type="text/html",
        text="Projects must use Widget SDK.\nSubmissions must include a demo video.",
    )


def wire_claim(span_id, **changes):
    value = {
        "source_id": "source_current",
        "normalized_field": "required_technology",
        "candidate_value": ["Widget SDK"],
        "supporting_span_id": span_id,
        "extraction_state": "CANDIDATE",
        "confidence": "HIGH",
    }
    value.update(changes)
    return value


def test_G08_G09_wire_claim_resolves_runtime_excerpt_and_rejects_model_excerpt():
    from qualor.runtime.extraction import ground_extraction_payload, validate_extraction_payload
    from qualor.runtime.spans import EvidenceSpanRegistry

    document = source()
    registry = EvidenceSpanRegistry(secret=b"a" * 32)
    span = registry.register(document, "required technology")[0]
    transport = validate_extraction_payload({"claims": [wire_claim(span.span_id)]})
    domain = ground_extraction_payload(transport, document, registry)

    assert domain.claims[0].excerpt == span.exact_text
    assert domain.claims[0].source_id == document.id
    assert domain.claims[0].source_url == document.final_url
    with pytest.raises(ValidationError):
        validate_extraction_payload(
            {"claims": [wire_claim(span.span_id, excerpt="model-authored replacement")]}
        )


def test_G05_G06_G07_grounding_rejects_invented_wrong_source_and_prior_run_span():
    from qualor.runtime.extraction import ground_extraction_payload, validate_extraction_payload
    from qualor.runtime.spans import EvidenceSpanRegistry

    document = source()
    current = EvidenceSpanRegistry(secret=b"a" * 32)
    valid = current.register(document, "technology")[0]
    invented = validate_extraction_payload(
        {"claims": [wire_claim("span_" + "f" * 32)]}
    )
    with pytest.raises(ValueError, match="SPAN_REFERENCE_NOT_FOUND"):
        ground_extraction_payload(invented, document, current)

    other = source(source_id="source_other")
    wrong_source = validate_extraction_payload(
        {"claims": [wire_claim(valid.span_id, source_id=other.id)]}
    )
    with pytest.raises(ValueError, match="EXTRACTION_SOURCE_REFERENCE_MISMATCH"):
        ground_extraction_payload(wrong_source, document, current)

    prior = EvidenceSpanRegistry(secret=b"b" * 32)
    prior_span = prior.register(document, "technology")[0]
    prior_payload = validate_extraction_payload(
        {"claims": [wire_claim(prior_span.span_id)]}
    )
    with pytest.raises(ValueError, match="SPAN_REFERENCE_NOT_FOUND"):
        ground_extraction_payload(prior_payload, document, current)


def test_G11_G12_bedrock_extractor_returns_grounded_claim_for_evidence_admission():
    from qualor.runtime.claims import validate_claim
    from qualor.runtime.extraction import BedrockClaimExtractor

    document = source()

    class Client:
        def converse(self, **request):
            body = json.loads(request["messages"][0]["content"][0]["text"])
            selected = next(
                item for item in body["EVIDENCE_SPANS"] if "Widget SDK" in item["exact_text"]
            )
            payload = {"claims": [wire_claim(selected["span_id"])]}
            return {
                "stopReason": "end_turn",
                "output": {"message": {"content": [{"text": json.dumps(payload)}]}},
                "usage": {"inputTokens": 100, "outputTokens": 100, "totalTokens": 200},
            }

    extracted = BedrockClaimExtractor(Client()).extract(document, "required technology")
    admitted = validate_claim(extracted[0], {document.id: document})

    assert admitted.evidence.supporting_excerpt in document.text
    assert admitted.evidence.source_id == document.id
    assert admitted.evidence.final_url == document.final_url
    assert admitted.support_state == "CONTROLLED_CLAUSE_VERIFIED"
