from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError


def metadata(record_id="example"):
    return dict(
        schema_version="1",
        id=record_id,
        version=1,
        created_at="2026-09-05T12:00:00Z",
        updated_at="2026-09-05T12:00:00Z",
        provenance="USER_ASSERTED",
    )


def test_A31_A32_A33_reward_kinds_and_pool_remain_distinct():
    from qualor.domain import Reward

    rewards = [
        Reward(
            **metadata(kind),
            kind=kind,
            amount={"currency": "USD", "amount": "20"},
            is_total_pool=pool,
        )
        for kind, pool in [
            ("CASH_PRIZE", False),
            ("CLOUD_CREDIT", False),
            ("EQUITY_INVESTMENT", False),
            ("GRANT", False),
            ("CASH_PRIZE", True),
        ]
    ]
    assert len({(r.kind, r.is_total_pool) for r in rewards}) == 5
    assert all(r.amount.amount == Decimal("20") for r in rewards)


@pytest.mark.parametrize("value", [0.1, True, "NaN", "Infinity", "-1"])
def test_A34_money_rejects_float_and_invalid_amounts(value):
    from qualor.domain import Money

    with pytest.raises(ValidationError):
        Money(currency="USD", amount=value)


def test_money_exactness_currency_and_ranges():
    from qualor.domain import Money, Reward

    assert Money(currency="EUR", amount="0.1").amount + Decimal("0.2") == Decimal("0.3")
    with pytest.raises(ValidationError):
        Money(currency="usd", amount="1")
    with pytest.raises(ValidationError):
        Reward(
            **metadata(),
            kind="GRANT",
            amount_min={"currency": "EUR", "amount": "3"},
            amount_max={"currency": "USD", "amount": "2"},
        )


def opportunity(**overrides):
    from qualor.domain import OpportunityRecord

    data = dict(
        metadata(),
        organizer="Example Foundation",
        program_name="  Demo   Award ",
        edition="2026",
        canonical_rules_url="https://example.org/rules?utm_source=test",
        application_url="https://example.org/apply",
        status="OPEN",
    )
    data.update(overrides)
    return OpportunityRecord(**data)


def test_A35_tracking_query_identity():
    a = opportunity()
    b = opportunity(
        canonical_rules_url="https://example.org/rules?utm_source=other&gclid=abc",
        program_name="demo award",
    )
    assert a.id == b.id
    assert a.canonical_rules_url == b.canonical_rules_url == "https://example.org/rules"


def test_A36_edition_changes_identity():
    assert opportunity().id != opportunity(edition="2027").id


def test_calendar_deadlines_remain_dates():
    record = opportunity(deadlines=["2026-09-20"])
    assert type(record.deadlines[0]) is date
    assert record.model_dump(mode="json")["deadlines"] == ["2026-09-20"]


def test_A37_naive_timestamp_rejected():
    from qualor.domain import FounderProfile

    data = metadata()
    data["created_at"] = datetime(2026, 9, 5)
    with pytest.raises(ValidationError):
        FounderProfile(**data)


def test_A38_aware_timestamps_normalize_utc():
    from qualor.domain import FounderProfile

    data = metadata()
    data["created_at"] = "2026-09-05T14:00:00+02:00"
    record = FounderProfile(**data)
    assert record.created_at == datetime(2026, 9, 5, 12, tzinfo=UTC)
    assert record.created_at.utcoffset().total_seconds() == 0


def test_A39_roundtrip_and_unknown_facts():
    from qualor.domain import FounderProfile

    record = FounderProfile(
        **metadata(), country_of_residence={"value": "Spain", "provenance": "USER_ASSERTED"}
    )
    assert FounderProfile.model_validate_json(record.model_dump_json()) == record
    assert record.citizenship.value is None
    assert record.citizenship.provenance.value == "UNKNOWN"


def test_A40_schema_version_required():
    from qualor.domain import FounderProfile

    data = metadata()
    del data["schema_version"]
    with pytest.raises(ValidationError):
        FounderProfile(**data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("legal_form", {"value": "Studio", "provenance": "USER_ASSERTED"}),
        ("team_size", {"value": "4", "provenance": "DOCUMENTED"}),
        ("citizenship", {"value": "Spain", "provenance": "UNKNOWN"}),
        ("country_of_residence", {"value": None, "provenance": "DOCUMENTED"}),
    ],
)
def test_profile_rejects_untyped_or_false_provenance(field, value):
    from qualor.domain import FounderProfile

    with pytest.raises(ValidationError):
        FounderProfile(**metadata(), **{field: value})


def test_project_facts_do_not_invent_traction_or_code_origin():
    from qualor.domain import ProjectProfile

    record = ProjectProfile(**metadata(), name="Synthetic project")
    assert record.stage.value is None
    assert record.code_provenance.value is None
    with pytest.raises(ValidationError):
        ProjectProfile(**metadata(), name="Synthetic", revenue=100)


def test_record_versions_order_and_mutation():
    from qualor.domain import FounderProfile

    data = metadata()
    data["version"] = 0
    with pytest.raises(ValidationError):
        FounderProfile(**data)
    data = metadata()
    data["updated_at"] = "2026-09-04T00:00:00Z"
    with pytest.raises(ValidationError):
        FounderProfile(**data)
    record = FounderProfile(**metadata())
    with pytest.raises(ValidationError):
        record.version = 2


def test_rule_cannot_supply_final_verdict():
    from qualor.domain import RuleCandidate

    with pytest.raises(ValidationError):
        RuleCandidate(
            **metadata(),
            rule_type="GEOGRAPHY",
            operator="EQ",
            operands=[],
            criticality="CRITICAL",
            evidence_ids=[],
            supported=True,
            source_text_summary="Synthetic",
            final_verdict="PASS",
        )


def test_evidence_preserves_original_source_urls():
    from qualor.domain import EvidenceRecord

    url = "https://synthetic.example/rules?utm_source=provided#condition"
    evidence = EvidenceRecord(
        **metadata(),
        original_url=url,
        final_url=url,
        retrieved_at="2026-09-05T12:00:00Z",
        source_type="SYNTHETIC_FIXTURE",
        content_hash="a" * 64,
        supporting_excerpt="Synthetic condition",
        normalized_field="GEOGRAPHY",
        extraction_state="REVIEWED",
    )
    assert evidence.original_url == url
    assert evidence.final_url == url
