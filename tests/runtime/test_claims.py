from datetime import UTC, datetime

import pytest


def source(text="Projects must use Widget SDK.", authority="OFFICIAL_RULES"):
    from qualor.runtime.sources import SourceDocument

    return SourceDocument(
        id="source_owned",
        original_url="https://example.org/rules",
        final_url="https://example.org/rules",
        retrieved_at=datetime.now(UTC),
        content_hash="a" * 64,
        authority=authority,
        text=text,
    )


def claim(**updates):
    from qualor.runtime.claims import ExtractedClaim

    values = dict(
        source_id="source_owned",
        source_url="https://example.org/rules",
        field="required_technology",
        value=["Widget SDK"],
        excerpt="Projects must use Widget SDK.",
        state="CANDIDATE",
        confidence="HIGH",
    )
    values.update(updates)
    return ExtractedClaim.model_validate(values)


def test_A06_official_supported_clause_gets_reviewed_source_evidence():
    from qualor.runtime.claims import validate_claim

    c = validate_claim(claim(), {"source_owned": source()})
    assert c.evidence.extraction_state == "REVIEWED"
    assert c.evidence.final_url == "https://example.org/rules"
    assert c.evidence.normalized_field == "REQUIRED_TECHNOLOGY"


def test_A07_third_party_cannot_review_critical_claim():
    from qualor.runtime.claims import validate_claim

    c = validate_claim(claim(), {"source_owned": source(authority="THIRD_PARTY")})
    assert c.evidence.extraction_state == "UNVERIFIED"


@pytest.mark.parametrize(
    "updates",
    [
        {"source_id": "missing"},
        {"source_url": "https://example.org/fake"},
        {"excerpt": "invented quote"},
        {"value": ["Invented SDK"]},
        {"field": "reward_conditions", "value": "1000000"},
        {"field": "deadline", "value": "2026-09-15T00:00:00Z"},
    ],
)
def test_A08_A30_unsupported_claim_rejected(updates):
    from qualor.runtime.claims import validate_claim

    with pytest.raises(ValueError):
        validate_claim(claim(**updates), {"source_owned": source()})


@pytest.mark.parametrize(
    "text",
    [
        "Projects are not required to use Widget SDK.",
        "Projects must use Widget SDK or Another SDK.",
        "For example, projects must use Widget SDK.",
    ],
)
def test_negation_alternatives_and_examples_not_reviewed(text):
    from qualor.runtime.claims import validate_claim

    c = validate_claim(claim(excerpt=text), {"source_owned": source(text)})
    assert c.evidence.extraction_state == "UNVERIFIED"


def test_unknown_and_unsupported_na_never_promoted():
    from qualor.runtime.claims import validate_claim

    c = validate_claim(claim(value=None, state="UNKNOWN"), {"source_owned": source()})
    assert c.evidence.extraction_state == "UNVERIFIED"
    with pytest.raises(ValueError):
        claim(value=None, state="NOT_APPLICABLE")


def test_A03_A04_final_verdict_fields_rejected():
    with pytest.raises(ValueError):
        claim(eligibility="PASS")
    with pytest.raises(ValueError):
        claim(recommendation="APPLY")


@pytest.mark.parametrize(
    "text",
    [
        "If entering the optional track, projects must use Widget SDK.",
        "Projects must use Widget SDK. This requirement does not apply to existing projects.",
    ],
)
def test_qualified_technology_claims_remain_unverified(text):
    from qualor.runtime.claims import validate_claim

    c = validate_claim(claim(excerpt=text), {"source_owned": source(text)})
    assert c.evidence.extraction_state == "UNVERIFIED"


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Projects must use Widget SDK2.", "MODEL_VALUE_CONFLICTS_WITH_SOURCE_NORMALIZATION"),
        ("Judges must use Widget SDK.", "NORMALIZED_VALUE_NOT_SUPPORTED_BY_QUOTE"),
    ],
)
def test_conflicting_or_unsupported_technology_proposal_is_rejected(text, reason):
    from qualor.runtime.claims import validate_claim

    with pytest.raises(ValueError, match=reason):
        validate_claim(claim(excerpt=text), {"source_owned": source(text)})


@pytest.mark.parametrize(
    "excerpt", ["Projects must use Widget SDK", "Projects must use Widget SDK."]
)
def test_source_exception_cannot_be_hidden_by_quote_punctuation(excerpt):
    from qualor.runtime.claims import validate_claim

    text = "Projects must use Widget SDK. This requirement does not apply to existing projects."
    admitted = validate_claim(claim(excerpt=excerpt), {"source_owned": source(text)})
    assert admitted.support_state == "QUOTE_ONLY"
