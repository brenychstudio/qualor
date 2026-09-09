"""Local product boundary integration with actual persisted fixture state."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qualor.decisions import DecisionFixture, decide_fixture
from qualor.persistence import Database
from qualor.workspace.models import RunEventPayload, RunRecord
from qualor.workspace.store import WorkspaceStore
from qualor.workspace.versioning import opportunity_semantic_digest

NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)
ORIGIN = "http://127.0.0.1:5173"


def seed(
    tmp_path,
    fixture_name="D01_ELIGIBLE_HIGH_SCORE_READY_APPLY",
    mode="FIXTURE",
    state="COMPLETED",
    decision_present=True,
    termination_reason=None,
    provider_state=None,
    official_evidence=False,
):
    fixture = DecisionFixture.model_validate_json(
        (Path(__file__).parent / "fixtures/decisions" / (fixture_name + ".json")).read_text()
    )
    if official_evidence:
        fixture = fixture.model_copy(
            update={
                "evidence": tuple(
                    e.model_copy(update={"source_type": "OFFICIAL_RULES"}) for e in fixture.evidence
                )
            }
        )
    decision = decide_fixture(fixture).selected_decision
    database = Database(tmp_path / "workspace.db")
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(fixture.founder)
        for project in fixture.projects:
            store.projects.put_project(project.project)
        store.opportunities.put_opportunity_version(
            fixture.opportunity, content_hash=opportunity_semantic_digest(fixture.opportunity)
        )
        for evidence in fixture.evidence:
            store.evidence.put_evidence(evidence, fixture.opportunity.id, 1)
        if decision_present and decision:
            store.decisions.put_decision(decision, founder_profile_id=fixture.founder.id)
        if provider_state is not None:
            assert "provider_state" in RunRecord.model_fields, (
                "Provider state must be persisted and typed"
            )
        store.runs.create_run(
            RunRecord(
                schema_version="1",
                id="research",
                version=1,
                created_at=NOW,
                updated_at=NOW,
                provenance="DOCUMENTED",
                mode=mode,
                state=state,
                opportunity_id=fixture.opportunity.id,
                opportunity_version=1,
                decision_id=decision.id if decision_present and decision else None,
                decision_version=1 if decision_present and decision else None,
                started_at=NOW,
                completed_at=NOW if state == "COMPLETED" else None,
                termination_reason=termination_reason,
                **({"provider_state": provider_state} if provider_state is not None else {}),
            )
        )
        for event in ("OPPORTUNITY_DISCOVERED", "DECISION_UPDATED"):
            store.runs.append_run_event(
                "research",
                event_type=event,
                payload=RunEventPayload(count=1),
                mode=mode,
                occurred_at=NOW,
            )
    return database, fixture, decision


def make_app(database, fixture=None, decision=None, *, readonly=False, now=NOW):
    import qualor.api as api
    from qualor.settings import Settings

    assert hasattr(api, "create_app"), "Task6 requires an application factory"
    return api.create_app(
        Settings(database_path=database.path, qualor_read_only_demo=readonly),
        actor_id=fixture.founder.id if fixture else "local-owner",
        policy_versions=decision.policy_versions if decision else None,
        mode="FIXTURE",
        clock=lambda: now,
    )


def client_for(app, host="127.0.0.1"):
    return TestClient(app, client=(host, 12345), raise_server_exceptions=False)


def headers(client):
    result = client.get("/api/v1/session", headers={"Origin": ORIGIN})
    assert result.status_code == 200
    return {"Origin": ORIGIN, "X-QUALOR-Action-Token": result.json()["action_token"]}


def test_empty_workspace_and_product_openapi(tmp_path):
    database = Database(tmp_path / "empty.db")
    app = make_app(database)
    assert not database.path.exists(), "constructing app must not create a database"
    with client_for(app) as client:
        empty_page = {"offset": 0, "limit": 50, "total": 0, "has_more": False}
        assert client.get("/api/v1/inbox").json() == {
            "items": [],
            "profile_present": False,
            "page": empty_page,
        }
        assert client.get("/api/v1/portfolio").json() == {"founder": None, "projects": []}
        assert client.get("/api/v1/runs").json() == {
            "runs": [],
            "events": [],
            "runs_page": empty_page,
            "events_page": empty_page,
        }
        schemas = app.openapi()["components"]["schemas"]
        assert {
            "InboxResponse",
            "OpportunityWorkspaceResponse",
            "EvidenceSheetView",
            "ApprovalRequest",
            "ApprovalView",
            "DraftPackView",
        } <= schemas.keys()


def test_every_read_route_and_real_activity(tmp_path):
    database, fixture, decision = seed(tmp_path)
    with client_for(make_app(database, fixture, decision)) as client:
        row = client.get("/api/v1/inbox").json()["items"][0]
        assert row["opportunity_id"] == fixture.opportunity.id
        assert row["recommendation"] == decision.recommendation
        assert row["run_state"] == "COMPLETED"
        assert row["mode"] == "FIXTURE"
        assert row["priority_rank"] == 0
        assert row["discovered_at"] == fixture.opportunity.created_at.isoformat().replace(
            "+00:00", "Z"
        )
        workspace = client.get(f"/api/v1/opportunities/{fixture.opportunity.id}/workspace").json()
        assert workspace["decision"]["best_project"]["id"] == decision.project_id
        assert workspace["decision"]["effort"] == decision.effort.model_dump(mode="json")
        assert workspace["decision"]["readiness"] == decision.readiness.model_dump(mode="json")
        assert workspace["decision"]["deadline"]["timezone_status"] == "UTC"
        sheet = client.get(f"/api/v1/opportunities/{fixture.opportunity.id}/evidence").json()
        proof = next(p for p in sheet["proofs"] if p["evidence_id"] == fixture.evidence[0].id)
        assert proof["excerpt"] == fixture.evidence[0].supporting_excerpt
        assert proof["url"] == fixture.evidence[0].final_url
        assert "technical_provenance" not in proof or proof["technical_provenance"] is None
        activity = client.get("/api/v1/runs/research/events").json()
        assert [e["sequence"] for e in activity["events"]] == [1, 2]
        assert [e["event_type"] for e in activity["events"]] == [
            "OPPORTUNITY_DISCOVERED",
            "DECISION_UPDATED",
        ]
        for route in ("/api/v1/inbox", "/api/v1/portfolio", "/api/v1/runs"):
            body = client.get(route).text.lower()
            assert all(
                word not in body
                for word in (
                    "action_token",
                    "record_json",
                    "raw_page",
                    "prompt",
                    "chain_of_thought",
                    "idempotency_key",
                    "hmac",
                    "database_path",
                )
            )


@pytest.mark.parametrize(
    "route",
    [
        "/api/v1/absent",
        "/api/v1/runs/no/events",
        "/api/v1/opportunities/no/workspace",
        "/api/v1/opportunities/no/evidence",
        "/api/v1/approvals/no",
        "/api/v1/draft-packs/no",
    ],
)
def test_bounded_not_found(tmp_path, route):
    with client_for(make_app(Database(tmp_path / "empty.db"))) as client:
        result = client.get(route)
        assert result.status_code == 404
        assert result.json() == {"code": "NOT_FOUND"}


@pytest.mark.parametrize(
    "host,origin,token",
    [
        ("192.0.2.1", ORIGIN, "valid"),
        ("127.0.0.1", "https://evil.example", "valid"),
        ("127.0.0.1", None, "valid"),
        ("127.0.0.1", ORIGIN, None),
        ("127.0.0.1", ORIGIN, "wrong"),
    ],
)
def test_mutation_guard_requires_all_three_checks(tmp_path, host, origin, token):
    app = make_app(Database(tmp_path / "empty.db"))
    with client_for(app) as local:
        good = headers(local)
        with client_for(app, host) as client:
            supplied = {}
            if origin:
                supplied["Origin"] = origin
            if token:
                supplied["X-QUALOR-Action-Token"] = (
                    good["X-QUALOR-Action-Token"] if token == "valid" else token
                )
            result = client.put("/api/v1/profile", json={}, headers=supplied)
            assert result.status_code == 403
            assert result.json() == {"code": "ACTION_FORBIDDEN"}


def test_validation_readonly_session_and_cors(tmp_path):
    app = make_app(Database(tmp_path / "empty.db"))
    with client_for(app) as client:
        assert client.get("/api/v1/session").status_code == 403
        assert (
            client.get("/api/v1/session", headers={"Origin": "https://evil.example"}).status_code
            == 403
        )
        result = client.put("/api/v1/profile", content='{"secret":', headers=headers(client))
        assert result.status_code == 422
        assert result.json() == {"code": "INVALID_REQUEST"}
        preflight = client.options(
            "/api/v1/profile",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "X-QUALOR-Action-Token",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == ORIGIN
    with client_for(make_app(Database(tmp_path / "demo.db"), readonly=True)) as client:
        for method, route in (
            ("PUT", "/api/v1/profile"),
            ("PUT", "/api/v1/projects/p"),
            ("POST", "/api/v1/opportunities/o/approvals"),
            ("POST", "/api/v1/approvals/a/confirm"),
        ):
            assert client.request(method, route, json={}).status_code == 404
        assert (
            client.get("/api/v1/session", headers={"Origin": ORIGIN}).json()["action_token"] is None
        )


def test_approval_confirm_draft_replay_and_restart(tmp_path):
    database, fixture, decision = seed(tmp_path)
    app = make_app(database, fixture, decision)
    with client_for(app) as client:
        guard = headers(client)
        workspace = client.get(f"/api/v1/opportunities/{fixture.opportunity.id}/workspace").json()
        request = workspace["decision"]["primary_action"]["approval_request"]
        assert request is not None
        pending = client.post(
            f"/api/v1/opportunities/{fixture.opportunity.id}/approvals", json=request, headers=guard
        )
        assert pending.status_code == 200, pending.text
        approval_id = pending.json()["id"]
        assert pending.json()["state"] == "PENDING_APPROVAL"
        body = {"expected_versions": request, "idempotency_key": "one-user-intent"}
        first = client.post(f"/api/v1/approvals/{approval_id}/confirm", json=body, headers=guard)
        assert first.status_code == 200, first.text
        assert first.json()["state"] == "DRAFT_READY"
        assert first.json()["draft_job"]["state"] == "COMPLETED"
        pack_id = first.json()["pack_id"]
        original = client.get(f"/api/v1/draft-packs/{pack_id}").json()
        assert len(original["sections"]) == 7
    with client_for(make_app(database, fixture, decision, now=NOW + timedelta(days=2))) as client:
        again = client.post(
            f"/api/v1/approvals/{approval_id}/confirm", json=body, headers=headers(client)
        )
        assert again.status_code == 200, again.text
        assert again.json()["pack_id"] == pack_id
        assert again.json()["draft_job"] == first.json()["draft_job"]
        assert client.get(f"/api/v1/draft-packs/{pack_id}").json() == original


def test_serve_is_loopback_only_and_no_token_output(monkeypatch):
    import uvicorn
    from typer.testing import CliRunner

    from qualor.cli import app

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))
    result = CliRunner().invoke(app, ["serve"])
    assert result.exit_code == 0, result.output
    assert calls[0]["host"] == "127.0.0.1"
    assert result.output.strip() == "http://127.0.0.1:8000"
    assert CliRunner().invoke(app, ["serve", "--host", "0.0.0.0"]).exit_code != 0


def test_portfolio_version_updates_and_conflicts(tmp_path):
    database, fixture, decision = seed(tmp_path)
    with client_for(make_app(database, fixture, decision)) as client:
        guard = headers(client)
        profile = fixture.founder.model_dump(mode="json")
        profile["constraints"] = ["New owner constraint"]
        request = {"expected_version": 1, "profile": profile}
        saved = client.put("/api/v1/profile", json=request, headers=guard)
        assert saved.status_code == 200, saved.text
        assert saved.json()["founder"]["version"] == 2
        assert saved.json()["founder"]["constraints"] == ["New owner constraint"]
        assert client.put("/api/v1/profile", json=request, headers=guard).json() == {
            "code": "VERSION_MISMATCH"
        }
        project = fixture.projects[0].project.model_dump(mode="json")
        project["name"] = "Renamed project"
        request = {"expected_version": 1, "project": project}
        saved = client.put(f"/api/v1/projects/{project['id']}", json=request, headers=guard)
        assert saved.status_code == 200, saved.text
        assert saved.json()["projects"][0]["version"] == 2
        assert (
            client.put("/api/v1/projects/another", json=request, headers=guard).status_code == 404
        )


@pytest.mark.parametrize(
    "scenario,code",
    [
        ("expired", "EXPIRED"),
        ("revoked", "REVOKED"),
        ("version", "VERSION_MISMATCH"),
        ("ambiguous", "AMBIGUOUS_EVIDENCE_REFERENCE"),
    ],
)
def test_http_cannot_bypass_approval_or_ambiguous_evidence(tmp_path, scenario, code):
    from qualor.workspace.models import ApprovalBindings, ApprovalChange

    database, fixture, decision = seed(tmp_path)
    app = make_app(database, fixture, decision)
    with client_for(app) as client:
        guard = headers(client)
        expected = client.get(f"/api/v1/opportunities/{fixture.opportunity.id}/workspace").json()[
            "decision"
        ]["primary_action"]["approval_request"]
        pending = client.post(
            f"/api/v1/opportunities/{fixture.opportunity.id}/approvals",
            json=expected,
            headers=guard,
        ).json()
        service = app.state.workspace
        if scenario == "expired":
            service.clock = lambda: NOW + timedelta(days=2)
        elif scenario == "revoked":
            service.approvals.revoke_invalid_approvals(
                ApprovalChange(opportunity_id=fixture.opportunity.id), NOW
            )
        elif scenario == "version":
            with database.transaction() as connection:
                WorkspaceStore(connection).projects.put_project(
                    fixture.projects[0].project.model_copy(update={"version": 2})
                )
        else:
            # Confirm first so ambiguity is detected through DraftingService's fail-closed adapter.
            service.approvals.confirm_approval(
                pending["id"],
                "intent",
                NOW,
                expected_versions=ApprovalBindings(
                    actor_id=fixture.founder.id, opportunity_id=fixture.opportunity.id, **expected
                ),
            )
            with database.transaction() as connection:
                evidence = fixture.evidence[0].model_copy(update={"version": 2})
                WorkspaceStore(connection).evidence.put_evidence(
                    evidence, fixture.opportunity.id, 1
                )
        result = client.post(
            f"/api/v1/approvals/{pending['id']}/confirm",
            json={"expected_versions": expected, "idempotency_key": "intent"},
            headers=guard,
        )
        assert result.status_code == 409, result.text
        assert result.json() == {"code": code}
        with database.transaction() as connection:
            assert connection.execute("SELECT count(*) FROM draft_packs").fetchone()[0] == 0


@pytest.mark.parametrize(
    "fixture_name,eligibility",
    [("D04_REVIEW_REQUIRED_WATCH", "REVIEW_REQUIRED"), ("D06_UNKNOWN_SCORE_WATCH", "PASS")],
)
def test_unknown_eligibility_and_unavailable_strategy(tmp_path, fixture_name, eligibility):
    database, fixture, decision = seed(tmp_path, fixture_name)
    with client_for(make_app(database, fixture, decision)) as client:
        canvas = client.get(f"/api/v1/opportunities/{fixture.opportunity.id}/workspace").json()[
            "decision"
        ]
        assert canvas["eligibility"] == eligibility
        assert canvas["recommendation"] == "WATCH"
        if decision.strategy_score is None:
            assert canvas["strategy"]["score"] is None
            assert canvas["strategy"]["state"] == "NOT_ENOUGH_EVIDENCE"
        assert not canvas["primary_action"]["available"]


def test_default_local_actor_reads_existing_single_founder(tmp_path):
    database, fixture, decision = seed(tmp_path)
    with client_for(make_app(database)) as client:
        assert client.get("/api/v1/portfolio").json()["founder"]["id"] == fixture.founder.id
        saved = client.put(
            "/api/v1/profile",
            json={"expected_version": 1, "profile": fixture.founder.model_dump(mode="json")},
            headers=headers(client),
        )
        assert saved.status_code == 200


def test_session_token_never_appears_in_readonly_or_read_contracts(tmp_path):
    app = make_app(Database(tmp_path / "empty.db"))
    with client_for(app) as client:
        token = headers(client)["X-QUALOR-Action-Token"]
        assert token not in repr(app.state.settings)
        for route in ("/api/v1/inbox", "/api/v1/runs", "/api/v1/portfolio"):
            assert token not in client.get(route).text
        assert (
            client.get("/api/v1/session", headers={"Origin": ORIGIN}).headers["cache-control"]
            == "no-store"
        )


def test_foreign_actor_approval_and_pack_are_not_found(tmp_path):
    database, fixture, decision = seed(tmp_path)
    with client_for(make_app(database, fixture, decision)) as client:
        guard = headers(client)
        expected = client.get(f"/api/v1/opportunities/{fixture.opportunity.id}/workspace").json()[
            "decision"
        ]["primary_action"]["approval_request"]
        approval = client.post(
            f"/api/v1/opportunities/{fixture.opportunity.id}/approvals",
            json=expected,
            headers=guard,
        ).json()
        result = client.post(
            f"/api/v1/approvals/{approval['id']}/confirm",
            json={"expected_versions": expected, "idempotency_key": "intent"},
            headers=guard,
        ).json()
    with client_for(make_app(database)) as client:
        assert client.get(f"/api/v1/approvals/{approval['id']}").status_code == 404
        assert client.get(f"/api/v1/draft-packs/{result['pack_id']}").status_code == 404


def test_errors_are_closed_typed_codes_and_never_exception_text(tmp_path, monkeypatch):
    import sqlite3

    from pydantic import ValidationError

    from qualor.workspace.read_models import ProductError

    with pytest.raises(ValidationError):
        ProductError(code="secret provider detail")
    with client_for(make_app(Database(tmp_path / "empty.db"))) as client:

        def broken():
            raise sqlite3.OperationalError("private C:/local/file.db secret password")

        monkeypatch.setattr(client.app.state.workspace, "inbox", broken)
        result = client.get("/api/v1/inbox")
        assert result.status_code == 500
        assert result.json() == {"code": "INTERNAL_ERROR"}


def test_reading_expired_approval_does_not_write_without_action_guard(tmp_path):
    database, fixture, decision = seed(tmp_path)
    app = make_app(database, fixture, decision)
    with client_for(app) as client:
        expected = client.get(f"/api/v1/opportunities/{fixture.opportunity.id}/workspace").json()[
            "decision"
        ]["primary_action"]["approval_request"]
        pending = client.post(
            f"/api/v1/opportunities/{fixture.opportunity.id}/approvals",
            json=expected,
            headers=headers(client),
        ).json()
        app.state.workspace.clock = lambda: NOW + timedelta(days=2)
        result = client.get(f"/api/v1/approvals/{pending['id']}")
        assert result.json()["reason"] == "EXPIRED"
        assert not result.json()["actionable"]
        with database.transaction() as connection:
            assert connection.execute("SELECT count(*) FROM approvals").fetchone()[0] == 1


def test_disconnected_provider_is_a_typed_activity_state(tmp_path):
    database, fixture, decision = seed(
        tmp_path, mode="LIVE", state="FAILED", provider_state="DISCONNECTED_LIVE_PROVIDER"
    )
    with client_for(make_app(database, fixture, decision)) as client:
        run = client.get("/api/v1/runs").json()["runs"][0]
        assert run["provider_state"] == "DISCONNECTED_LIVE_PROVIDER"
        assert run["mode"] == "LIVE"
        assert run["state"] == "FAILED"


def test_policy_free_repository_enumeration_returns_current_typed_records(tmp_path):
    database, fixture, decision = seed(tmp_path)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        for repository in (store.profiles, store.projects, store.opportunities, store.runs):
            assert hasattr(repository, "list_current"), (
                "Product enumeration belongs in repositories"
            )
        store.profiles.put_founder(fixture.founder.model_copy(update={"version": 2}))
        assert [p.version for p in store.profiles.list_current()] == [2]
        assert [p.id for p in store.projects.list_current()] == [fixture.projects[0].project.id]
        assert [p.id for p in store.opportunities.list_current()] == [fixture.opportunity.id]
        assert [r.id for r in store.runs.list_current()] == ["research"]
        assert store.runs.current("research").id == "research"
        assert store.runs.current("missing") is None


def test_no_results_is_distinct_from_empty_profile(tmp_path):
    source, fixture, _ = seed(tmp_path / "fixture")
    database = Database(tmp_path / "empty.db")
    with database.transaction() as connection:
        WorkspaceStore(connection).profiles.put_founder(fixture.founder)
    with client_for(make_app(database)) as client:
        assert client.get("/api/v1/inbox").json() == {
            "items": [],
            "profile_present": True,
            "page": {"offset": 0, "limit": 50, "total": 0, "has_more": False},
        }


@pytest.mark.parametrize("origin", ["*", "https://evil.example", "null", "http://localhost/path"])
def test_settings_reject_untrusted_allowed_origins(origin):
    from pydantic import ValidationError

    from qualor.settings import Settings

    with pytest.raises(ValidationError):
        Settings(qualor_allowed_origins=(origin,))
