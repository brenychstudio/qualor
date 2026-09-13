"""Hosted approval composes existing LIVE authority; no external submission."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from test_hosted_live_runs import AUTH, SECRET

from qualor.api import create_app
from qualor.decisions import DecisionFixture
from qualor.decisions.engine import decide
from qualor.decisions.fixture import DecisionInput
from qualor.persistence import Database
from qualor.runtime.run_models import StudioInput
from qualor.settings import Settings
from qualor.workspace.models import RunEventPayload, RunRecord
from qualor.workspace.store import WorkspaceStore
from qualor.workspace.versioning import opportunity_semantic_digest

NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)
SOURCE = Path(__file__).parent / "fixtures/decisions/D01_ELIGIBLE_HIGH_SCORE_READY_APPLY.json"


def hosted_graph(tmp_path):
    source = DecisionFixture.model_validate_json(SOURCE.read_text(encoding="utf-8"))
    project_input = source.projects[0].model_copy(
        update={"project": source.projects[0].project.model_copy(update={"name": "QUALOR"})}
    )
    evidence = tuple(
        item.model_copy(
            update={
                "source_type": "OFFICIAL_RULES",
                "original_url": "https://example.org/official-rules",
                "final_url": "https://example.org/official-rules",
            }
        )
        for item in source.evidence
    )
    opportunity = source.opportunity.model_copy(
        update={"canonical_rules_url": "https://example.org/official-rules"}
    )
    decision_input = DecisionInput.model_validate(
        {
            **source.model_dump(),
            "mode": "LIVE",
            "opportunity": opportunity,
            "evidence": evidence,
            "projects": (project_input,),
        }
    )
    output = decide(decision_input)
    decision = output.selected_decision
    assert decision is not None and decision.recommendation == "APPLY"

    database = Database(tmp_path / "hosted-approval.db")
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(source.founder)
        store.projects.put_project(project_input.project)
        store.opportunities.put_opportunity_version(
            opportunity, content_hash=opportunity_semantic_digest(opportunity)
        )
        for item in evidence:
            store.evidence.put_evidence(item, opportunity.id, opportunity.version)
        store.decisions.put_decision(decision, founder_profile_id=source.founder.id)
        store.runs.create_run(
            RunRecord(
                schema_version="1",
                id="controlled-live-run",
                version=1,
                created_at=NOW,
                updated_at=NOW,
                provenance="DOCUMENTED",
                mode="LIVE",
                state="COMPLETED",
                opportunity_id=opportunity.id,
                opportunity_version=opportunity.version,
                decision_id=decision.id,
                decision_version=decision.version,
                started_at=NOW,
                completed_at=NOW,
                termination_reason="SUFFICIENT_CRITICAL_EVIDENCE",
            )
        )
        store.runs.append_run_event(
            "controlled-live-run",
            event_type="DECISION_EVALUATED",
            payload=RunEventPayload(count=1),
            mode="LIVE",
            occurred_at=NOW,
        )

    profile = StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Controlled hosted approval",
        allowed_hosts=("example.org",),
        founder=decision_input.founder,
        projects=(project_input,),
    )
    profile_path = tmp_path / "hosted-profile.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")
    settings = Settings(
        database_path=database.path,
        qualor_security_mode="HOSTED_DEMO",
        qualor_origin_auth=SECRET,
        qualor_demo_profile_path=profile_path,
        qualor_gateway_id="controlled-gateway",
    )
    return settings, decision_input, decision, profile


def browser_headers(client):
    session = client.get("/api/v1/session", headers=AUTH)
    assert session.status_code == 200
    return {**AUTH, "X-QUALOR-Action-Token": session.json()["action_token"]}


def test_hosted_live_approval_confirm_pack_and_restart(tmp_path):
    settings, source, _, profile = hosted_graph(tmp_path)
    opportunity_id = source.opportunity.id
    app = create_app(settings, clock=lambda: NOW)
    with (
        patch("qualor.hosted.inputs.load_demo_profile", return_value=profile),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        workspace = client.get(
            f"/api/v1/opportunities/{opportunity_id}/workspace", headers=AUTH
        ).json()
        approval_request = workspace["decision"]["primary_action"]["approval_request"]
        assert workspace["mode"] == "LIVE"
        assert workspace["decision"]["primary_action"]["available"] is True
        assert approval_request is not None

        headers = browser_headers(client)
        pending = client.post(
            f"/api/v1/opportunities/{opportunity_id}/approvals",
            headers=headers,
            json=approval_request,
        )
        assert pending.status_code == 200, pending.text
        assert pending.json()["state"] == "PENDING_APPROVAL"

        repeated = client.post(
            f"/api/v1/opportunities/{opportunity_id}/approvals",
            headers=headers,
            json=approval_request,
        )
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["id"] == pending.json()["id"]

        # A refresh gets a different in-memory capability while durable approval remains.
        refreshed_headers = browser_headers(client)
        assert refreshed_headers["X-QUALOR-Action-Token"] != headers["X-QUALOR-Action-Token"]
        assert (
            client.get(f"/api/v1/approvals/{pending.json()['id']}", headers=AUTH).json()["state"]
            == "PENDING_APPROVAL"
        )

        body = {
            "expected_versions": approval_request,
            "idempotency_key": "one-hosted-human-intent",
        }
        confirmed = client.post(
            f"/api/v1/approvals/{pending.json()['id']}/confirm",
            headers=refreshed_headers,
            json=body,
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["state"] == "DRAFT_READY"
        pack_id = confirmed.json()["pack_id"]
        pack = client.get(f"/api/v1/draft-packs/{pack_id}", headers=AUTH)
        assert pack.status_code == 200
        assert pack.json()["mode"] == "LIVE"
        assert len(pack.json()["sections"]) == 7

        retry = client.post(
            f"/api/v1/approvals/{pending.json()['id']}/confirm",
            headers=refreshed_headers,
            json=body,
        )
        assert retry.status_code == 200
        assert retry.json()["pack_id"] == pack_id
        different_intent = client.post(
            f"/api/v1/approvals/{pending.json()['id']}/confirm",
            headers=refreshed_headers,
            json={**body, "idempotency_key": "different-human-intent"},
        )
        assert different_intent.status_code == 409
        with Database(settings.database_path).transaction() as connection:
            assert connection.execute("SELECT COUNT(DISTINCT id) FROM approvals").fetchone()[0] == 1
            assert connection.execute("SELECT COUNT(*) FROM draft_packs").fetchone()[0] == 1

    with (
        patch("qualor.hosted.inputs.load_demo_profile", return_value=profile),
        TestClient(
            create_app(settings, clock=lambda: NOW + timedelta(hours=1)),
            raise_server_exceptions=False,
        ) as reopened,
    ):
        persisted = reopened.get(f"/api/v1/draft-packs/{pack_id}", headers=AUTH)
        assert persisted.status_code == 200
        assert persisted.json() == pack.json()


def test_hosted_approval_cannot_be_retargeted_to_stale_versions(tmp_path):
    settings, source, _, profile = hosted_graph(tmp_path)
    opportunity_id = source.opportunity.id
    with (
        patch("qualor.hosted.inputs.load_demo_profile", return_value=profile),
        TestClient(
            create_app(settings, clock=lambda: NOW), raise_server_exceptions=False
        ) as client,
    ):
        workspace = client.get(
            f"/api/v1/opportunities/{opportunity_id}/workspace", headers=AUTH
        ).json()
        request = workspace["decision"]["primary_action"]["approval_request"]
        stale = {**request, "decision_version": request["decision_version"] + 1}
        result = client.post(
            f"/api/v1/opportunities/{opportunity_id}/approvals",
            headers=browser_headers(client),
            json=stale,
        )
        assert result.status_code == 409
        assert result.json()["code"] in {"VERSION_MISMATCH", "GRAPH_MISMATCH"}
        with Database(settings.database_path).transaction() as connection:
            assert connection.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0


def test_hosted_api_registers_no_external_submission_route(tmp_path):
    settings, _, _, _ = hosted_graph(tmp_path)
    app = create_app(settings, clock=lambda: NOW)
    forbidden = ("submit", "send", "publish", "dispatch", "email", "webhook")
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert not [path for path in paths if any(term in path.lower() for term in forbidden)]
