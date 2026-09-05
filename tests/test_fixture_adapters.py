import asyncio
import json
import socket
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from typer.testing import CliRunner

from qualor.api import app as api
from qualor.cli import app as cli

FIXTURES = Path(__file__).parent / "fixtures"


def post_fixture(payload):
    async def request():
        async with AsyncClient(transport=ASGITransport(api), base_url="http://qualor") as client:
            return await client.post("/dev/evaluate-fixture", json=payload)

    return asyncio.run(request())


@pytest.fixture
def payload():
    return json.loads((FIXTURES / "F01_FULL_PASS.json").read_text())


@pytest.mark.parametrize(
    "name,expected",
    [
        ("F01_FULL_PASS", "PASS"),
        ("F02_HARD_LEGAL_FAIL", "FAIL"),
        ("F03_UNKNOWN_LEGAL_STATUS", "REVIEW_REQUIRED"),
        ("F04_STALE_CRITICAL_EVIDENCE", "REVIEW_REQUIRED"),
        ("F05_INCOMPLETE_COVERAGE", "REVIEW_REQUIRED"),
        ("F06_OR_ALTERNATIVE_PASS", "PASS"),
        ("F07_OR_UNRESOLVED", "REVIEW_REQUIRED"),
        ("F08_NEW_PROJECT_PROVENANCE_UNKNOWN", "REVIEW_REQUIRED"),
    ],
)
def test_cli_fixture_results_are_labeled_and_offline(name, expected, monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("No network allowed")

    monkeypatch.setattr(socket.socket, "connect", denied)
    result = CliRunner().invoke(cli, ["evaluate-fixture", str(FIXTURES / (name + ".json"))])
    assert result.exit_code == 0, result.output
    assert "MODE=FIXTURE" in result.output
    assert "ELIGIBILITY=" + expected in result.output
    assert '"state": "' + expected + '"' in result.output
    assert "MODE=LIVE" not in result.output


def test_cli_invalid_fixture_has_nonzero_exit(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"mode":"LIVE"}')
    result = CliRunner().invoke(cli, ["evaluate-fixture", str(path)])
    assert result.exit_code != 0
    assert "INVALID_FIXTURE" in result.output


def test_api_fixture_result(payload):
    response = post_fixture(payload)
    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "FIXTURE"
    assert result["eligibility"] == "PASS"
    assert len(result["evaluations"]) == 9
    assert len(result["coverage"]) == 9
    assert result["missing_information"] == []


def test_api_does_not_accept_filesystem_path():
    response = post_fixture({"path": "private-file.json"})
    assert response.status_code == 422


@pytest.mark.parametrize("mutation", ["live", "verdict", "duplicate", "criticality"])
def test_api_rejects_invalid_or_forged_fixture(payload, mutation):
    if mutation == "live":
        payload["mode"] = "LIVE"
    elif mutation == "verdict":
        payload["eligibility"] = "PASS"
    elif mutation == "duplicate":
        payload["rules"].append(payload["rules"][0])
    else:
        child = dict(payload["rules"][0], id="child", criticality="NON_CRITICAL")
        payload["rules"][0].update(
            operator="AND", operands=[], subject_reference=None, children=[child]
        )
    assert post_fixture(payload).status_code == 422


def test_api_fixture_route_disabled_outside_development(payload, monkeypatch):
    monkeypatch.setenv("QUALOR_ENV", "production")
    assert post_fixture(payload).status_code == 404
