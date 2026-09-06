"""Offline B3K measurement: owned claims and sanitized J usage counters only.

Projection is conditional on the four observed planner input counts. It is not
a whole-run worst-case reservation; every future call still uses the real guard.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal

from qualor.runtime.agent import INPUT_RATE, OUTPUT_RATE, estimate_model_reservation
from qualor.runtime.extraction import MAX_EXTRACTED_CLAIMS_PER_CALL, build_extraction_request
from qualor.runtime.model_policy import EXTRACTION_MAX_OUTPUT_TOKENS, STRANDS_MAX_OUTPUT_TOKENS
from qualor.runtime.sources import SourceDocument


def owned_output(count):
    base = {
        "source_id": "source_" + "a" * 32,
        "extraction_state": "CANDIDATE",
        "confidence": "HIGH",
        "not_applicable_reason": None,
    }
    # Owned replay technology clause plus explicit synthetic sizing assumptions.
    # Distinct claims model a focused batch, not duplicated claims or live rules.
    facts = [
        (
            "required_technology",
            ["Widget SDK"],
            (
                "Projects must use Widget SDK. The submitted demonstration must show "
                "this integration working."
            ),
        ),
        (
            "project_policy",
            "NEW_ONLY",
            (
                "Projects must be new. Development of the submitted project must start during "
                "the contest period; pre-existing projects are not eligible for this track."
            ),
        ),
        ("license", "MIT", "Submitted source code must be distributed under the MIT license."),
        (
            "deliverables",
            ["demo video", "architecture diagram"],
            "Each submission must include a demo video and an architecture diagram.",
        ),
        (
            "deadline",
            "2026-09-30T17:00:00Z",
            "The submission deadline is 2026-09-30T17:00:00Z (UTC).",
        ),
    ]
    return {
        "claims": [
            {
                **base,
                "normalized_field": field,
                "candidate_value": value,
                "supporting_span_id": "span_" + str(index).zfill(32),
            }
            for index, (field, value, _excerpt) in enumerate(facts[:count], start=1)
        ]
    }


def measure():
    sizes = {
        str(n): len(json.dumps(owned_output(n), ensure_ascii=False).encode("utf-8"))
        for n in (1, 2, 3, 5)
    }
    source = SourceDocument(
        id="source_" + "a" * 32,
        original_url="https://example.org/official/professional-agents/rules",
        final_url="https://example.org/official/professional-agents/rules",
        retrieved_at=datetime(2026, 9, 6, tzinfo=UTC),
        content_hash="a" * 64,
        authority="OFFICIAL_RULES",
        content_type="text/html",
        text=("Projects must use Widget SDK." + " x" * 30_000)[:60_000],
    )
    request = build_extraction_request(
        source, "required technology", max_output_tokens=EXTRACTION_MAX_OUTPUT_TOKENS
    )
    # Request byte upper bound is the larger of the reconstructed focused request
    # and J's measured first extraction request. The existing estimator adds 2048.
    extraction_bytes = max(11972, len(json.dumps(request, ensure_ascii=False).encode()))
    input_cost = (Decimal(2402 + 3575 + 4401 + 4888) + extraction_bytes + 2048) * INPUT_RATE
    output_cost = (
        Decimal(4 * STRANDS_MAX_OUTPUT_TOKENS + EXTRACTION_MAX_OUTPUT_TOKENS) * OUTPUT_RATE
    )
    search_cost = Decimal("0.014")
    gateway_allowance = Decimal("0.004")  # existing USD 0.002/query allowance
    return {
        "estimated_output_tokens_by_claim_count": sizes,
        "estimator": "UTF8_BYTE_UPPER_BOUND_NOT_PROVIDER_TOKEN_COUNT",
        "max_claims_per_extraction": MAX_EXTRACTED_CLAIMS_PER_CALL,
        "strands_max_output_tokens": STRANDS_MAX_OUTPUT_TOKENS,
        "extraction_max_output_tokens": EXTRACTION_MAX_OUTPUT_TOKENS,
        "projected_bedrock_calls": 5,
        "projected_input_cost_usd": input_cost,
        "projected_output_cost_usd": output_cost,
        "projected_search_cost_usd": search_cost,
        "projected_gateway_cost_usd": gateway_allowance,
        "projected_total_run_cost_usd": input_cost + output_cost + search_cost + gateway_allowance,
        "focused_extraction_reservation_usd": estimate_model_reservation(request),
        "projection_basis": (
            "FOUR_HISTORICAL_PLANNER_INPUT_COUNTS_PLUS_ONE_EXTRACTION; "
            "DETERMINISTIC_FINALIZATION_NO_EXTRA_MODEL_TURN"
        ),
    }


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2, default=str))
