import hashlib
import json
import socket
from pathlib import Path

import pytest

from qualor.domain.fixture import FixtureInput
from qualor.eligibility import aggregate_eligibility

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLD = [
    ("F01_FULL_PASS", "PASS"),
    ("F02_HARD_LEGAL_FAIL", "FAIL"),
    ("F03_UNKNOWN_LEGAL_STATUS", "REVIEW_REQUIRED"),
    ("F04_STALE_CRITICAL_EVIDENCE", "REVIEW_REQUIRED"),
    ("F05_INCOMPLETE_COVERAGE", "REVIEW_REQUIRED"),
    ("F06_OR_ALTERNATIVE_PASS", "PASS"),
    ("F07_OR_UNRESOLVED", "REVIEW_REQUIRED"),
    ("F08_NEW_PROJECT_PROVENANCE_UNKNOWN", "REVIEW_REQUIRED"),
]


@pytest.mark.parametrize("name,expected", GOLD)
def test_gold_fixture_offline(name, expected, monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Fixture evaluation attempted a network operation")

    monkeypatch.setattr(socket.socket, "connect", denied)
    fixture = FixtureInput.model_validate_json((FIXTURES / (name + ".json")).read_text())
    assert fixture.mode == "FIXTURE"
    gate = aggregate_eligibility(fixture.rules, fixture.context)
    assert gate.state == expected
    assert aggregate_eligibility(fixture.rules, fixture.context) == gate
    assert type(gate).model_validate_json(gate.model_dump_json()) == gate


def test_gold_fixture_matrix_has_all_cases_and_full_pass_is_fully_evaluated():
    assert len(list(FIXTURES.glob("F*.json"))) == 8
    fixture = FixtureInput.model_validate(json.loads((FIXTURES / "F01_FULL_PASS.json").read_text()))
    gate = aggregate_eligibility(fixture.rules, fixture.context)
    assert all(entry.state == "EVALUATED" for entry in gate.critical_coverage)
    assert all(item.status == "PASS" for item in gate.evaluations)


@pytest.mark.parametrize("name,expected", GOLD)
def test_owned_fixture_snapshot_hashes(name, expected):
    fixture = FixtureInput.model_validate_json((FIXTURES / (name + ".json")).read_text())
    for evidence in fixture.context.evidence:
        # The complete owned snapshot is this short authored text, not a fetched page.
        assert (
            evidence.content_hash
            == hashlib.sha256(evidence.supporting_excerpt.encode("utf-8")).hexdigest()
        )
