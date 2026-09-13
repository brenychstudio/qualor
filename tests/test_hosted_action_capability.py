"""Hosted browser capability boundary; no provider or paid execution."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from test_hosted_live_runs import AUTH, SECRET, ControlledRunner, config, make_app

from qualor.api import create_app
from qualor.settings import Settings


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 13, 12, tzinfo=UTC)

    def __call__(self):
        return self.now


def test_hosted_capabilities_are_random_expiring_bounded_and_constant_time(monkeypatch):
    import qualor.hosted.capabilities as module

    clock = Clock()
    registry = module.HostedActionCapabilities(ttl=timedelta(minutes=30), maximum=2, clock=clock)
    first = registry.issue()
    second = registry.issue()

    assert first != second
    assert registry.validate(first)
    assert registry.validate(second)

    compared = []
    original = module.hmac.compare_digest

    def observed(left, right):
        compared.append((left, right))
        return original(left, right)

    monkeypatch.setattr(module.hmac, "compare_digest", observed)
    assert not registry.validate("wrong-capability")
    assert compared

    third = registry.issue()
    assert registry.size == 2
    assert not registry.validate(first)
    assert registry.validate(third)

    clock.now += timedelta(minutes=30)
    assert not registry.validate(second)
    assert not registry.validate(third)
    assert registry.size == 0


def test_hosted_session_requires_proxy_and_issues_memory_only_capability(tmp_path, caplog):
    with TestClient(make_app(config(tmp_path), ControlledRunner())) as client:
        assert client.get("/api/v1/session").status_code == 403
        first = client.get("/api/v1/session", headers=AUTH)
        second = client.get("/api/v1/session", headers=AUTH)

        assert first.status_code == second.status_code == 200
        assert first.json()["read_only"] is False
        assert first.json()["action_token"]
        assert first.json()["action_token"] != second.json()["action_token"]
        assert client.app.state.action_token is None
        assert first.json()["action_token"] not in caplog.text


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        (AUTH, 403),
        ({"X-QUALOR-Action-Token": "browser-only"}, 403),
        ({**AUTH, "X-QUALOR-Action-Token": "wrong"}, 403),
    ],
)
def test_hosted_approval_requires_proxy_and_capability(tmp_path, headers, expected):
    with TestClient(make_app(config(tmp_path), ControlledRunner())) as client:
        result = client.post("/api/v1/opportunities/missing/approvals", headers=headers, json={})
        assert result.status_code == expected
        assert result.json() == {"code": "ACTION_FORBIDDEN"}


def test_valid_hosted_proxy_and_capability_reach_existing_approval_route(tmp_path):
    with TestClient(make_app(config(tmp_path), ControlledRunner())) as client:
        token = client.get("/api/v1/session", headers=AUTH).json()["action_token"]
        result = client.post(
            "/api/v1/opportunities/missing/approvals",
            headers={**AUTH, "X-QUALOR-Action-Token": token},
            json={},
        )

    assert result.status_code in {404, 422}
    assert result.json()["code"] != "ACTION_FORBIDDEN"


def test_hosted_mutation_rejects_ambiguous_capability_headers(tmp_path):
    with TestClient(make_app(config(tmp_path), ControlledRunner())) as client:
        token = client.get("/api/v1/session", headers=AUTH).json()["action_token"]
        result = client.post(
            "/api/v1/opportunities/missing/approvals",
            headers=[
                ("X-QUALOR-Origin-Auth", SECRET),
                ("X-QUALOR-Action-Token", token),
                ("X-QUALOR-Action-Token", token),
            ],
            json={},
        )

    assert result.status_code == 403
    assert result.json() == {"code": "ACTION_FORBIDDEN"}


def test_local_session_and_owner_mutation_boundary_remain_unchanged(tmp_path):
    settings = Settings(database_path=tmp_path / "local.db")
    with TestClient(
        create_app(settings), client=("127.0.0.1", 3456), raise_server_exceptions=False
    ) as client:
        origin = {"Origin": "http://127.0.0.1:5173"}
        session = client.get("/api/v1/session", headers=origin)
        token = session.json()["action_token"]

        assert session.status_code == 200
        assert session.json()["read_only"] is False
        assert client.put("/api/v1/profile", headers=origin, json={}).status_code == 403
        reached = client.put(
            "/api/v1/profile",
            headers={**origin, "X-QUALOR-Action-Token": token},
            json={},
        )
        assert reached.status_code == 422


def test_hosted_read_only_demo_refuses_approval_without_dereferencing_registry(tmp_path):
    settings = config(tmp_path).model_copy(
        update={"qualor_read_only_demo": True, "qualor_hosted_live_enabled": False}
    )
    with TestClient(
        make_app(settings, ControlledRunner()), raise_server_exceptions=False
    ) as client:
        result = client.post(
            "/api/v1/opportunities/missing/approvals",
            headers=AUTH,
            json={},
        )

    assert result.status_code == 404
    assert result.json() == {"code": "NOT_FOUND"}
