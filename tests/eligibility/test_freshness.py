from datetime import UTC, date, datetime, timedelta

import pytest

NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "age,remaining,expected",
    [
        (23.99, 100, "FRESH"),
        (24, 100, "STALE"),
        (25, 100, "STALE"),
        (5.99, 71, "FRESH"),
        (6, 71, "STALE"),
        (8, 71, "STALE"),
        (8, 72, "FRESH"),
        (-1, 100, "UNKNOWN"),
        (7, -1, "STALE"),
    ],
)
def test_A28_A29_freshness_boundaries(age, remaining, expected):
    from qualor.eligibility import evaluate_freshness

    assert (
        evaluate_freshness(NOW - timedelta(hours=age), NOW, NOW + timedelta(hours=remaining))
        == expected
    )


def test_A30_failed_refresh_does_not_replace_snapshot():
    from qualor.domain import EvidenceRecord
    from qualor.eligibility import evaluate_freshness

    evidence = EvidenceRecord(
        schema_version="1",
        id="e",
        version=1,
        created_at=NOW - timedelta(days=2),
        updated_at=NOW,
        provenance="DOCUMENTED",
        original_url="https://synthetic.example/rules",
        final_url="https://synthetic.example/rules",
        retrieved_at=NOW - timedelta(hours=25),
        source_type="SYNTHETIC_FIXTURE",
        content_hash="a" * 64,
        supporting_excerpt="Owned synthetic rule",
        normalized_field="GEOGRAPHY",
        extraction_state="REVIEWED",
        last_refresh_failed_at=NOW,
    )
    assert evaluate_freshness(evidence.retrieved_at, NOW) == "STALE"


def test_unknown_calendar_timezone_conservative_and_naive_rejected():
    from qualor.eligibility import evaluate_freshness

    assert evaluate_freshness(NOW - timedelta(hours=7), NOW, date(2026, 9, 20)) == "STALE"
    with pytest.raises(ValueError):
        evaluate_freshness(datetime(2026, 9, 5), NOW)
