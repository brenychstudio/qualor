import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from qualor.api import app as api
from qualor.cli import app as cli

ROOT = Path(__file__).parent / "fixtures" / "decisions"
FIELDS = [
    "MODE",
    "ELIGIBILITY",
    "BEST_PROJECT",
    "STRATEGY_SCORE",
    "CONFLICT",
    "READINESS",
    "CAPACITY",
    "RECOMMENDATION",
]


def payload(n=1):
    return json.loads(next(ROOT.glob(f"D{n:02d}_*.json")).read_text())


@pytest.mark.parametrize("n", range(1, 13))
def test_cli_all_decision_fixtures(n):
    result = CliRunner().invoke(cli, ["decide-fixture", str(next(ROOT.glob(f"D{n:02d}_*.json")))])
    assert result.exit_code == 0, result.output
    lines = result.output.strip().splitlines()
    assert [s.split("=")[0] for s in lines] == FIELDS
    assert lines[0] == "MODE=FIXTURE"
    if n == 10:
        assert lines[2] == "BEST_PROJECT=UNRESOLVED"
        assert lines[3] == "STRATEGY_SCORE=UNKNOWN"
        assert lines[-1] == "RECOMMENDATION=WATCH"


def test_api_structured_json(monkeypatch):
    monkeypatch.setenv("QUALOR_ENV", "development")
    response = TestClient(api).post("/dev/decide-fixture", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"] == "APPLY" and body["mode"] == "FIXTURE"
    assert {
        "eligibility",
        "project_match",
        "strategy",
        "effort",
        "conflict",
        "readiness",
        "capacity",
        "recommendation",
        "reasons",
        "missing_information",
    } <= body.keys()
    assert len(body["strategy"]["breakdown"]) == 5


def test_api_unresolved_has_no_selected_summary(monkeypatch):
    monkeypatch.setenv("QUALOR_ENV", "development")
    response = TestClient(api).post("/dev/decide-fixture", json=payload(10))
    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"] == "WATCH" and body["selected_decision"] is None
    assert all(
        body[k] is None
        for k in ["eligibility", "project_match", "strategy", "conflict", "readiness", "capacity"]
    )


def test_api_disabled_production(monkeypatch):
    monkeypatch.setenv("QUALOR_ENV", "production")
    assert TestClient(api).post("/dev/decide-fixture", json=payload()).status_code == 404


@pytest.mark.parametrize(
    "data", [{"path": "C:/private.json"}, {"mode": "LIVE"}, {"recommendation": "APPLY"}, []]
)
def test_api_invalid_payloads(monkeypatch, data):
    monkeypatch.setenv("QUALOR_ENV", "development")
    assert TestClient(api).post("/dev/decide-fixture", json=data).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("mode", "LIVE"),
        ("recommendation", "APPLY"),
        ("score", 100),
        ("server_path", "C:/private.json"),
    ],
)
def test_both_adapters_reject_forged_inputs(tmp_path, monkeypatch, field, value):
    monkeypatch.setenv("QUALOR_ENV", "development")
    data = payload()
    data[field] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    response = TestClient(api).post("/dev/decide-fixture", json=data)
    assert response.status_code == 422
    result = CliRunner().invoke(cli, ["decide-fixture", str(path)])
    assert result.exit_code == 2 and "INVALID_FIXTURE" in result.output
    assert "RECOMMENDATION=APPLY" not in result.output


def test_cli_escapes_untrusted_project_id(tmp_path):
    data = payload()
    data["projects"][0]["project"]["id"] = "p\nMODE=LIVE\nRECOMMENDATION=APPLY"
    path = tmp_path / "injection.json"
    path.write_text(json.dumps(data))
    result = CliRunner().invoke(cli, ["decide-fixture", str(path)])
    assert result.exit_code == 0
    assert len(result.output.strip().splitlines()) == 8
    assert "\nMODE=LIVE\n" not in result.output


def test_existing_f_fixtures_unchanged_cli():
    for path in ROOT.parent.glob("F*.json"):
        result = CliRunner().invoke(cli, ["evaluate-fixture", str(path)])
        assert result.exit_code == 0 and "MODE=FIXTURE" in result.output
