"""End-to-end acceptance for the whole QUALOR workspace.

One repeatable scenario drives the real services from an owned FIXTURE file all the way to
an immutable Application Pack, then closes and reopens the database to prove the state was
durable rather than remembered. Nothing here mocks persistence and nothing injects an
authoritative result: the fixtures supply inputs and QUALOR supplies every verdict.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qualor.decisions import DecisionFixture, decide_fixture
from qualor.persistence import Database
from qualor.workspace import WorkspaceStore
from qualor.workspace.lifecycle import WorkspaceLifecycle
from qualor.workspace.models import RunEventPayload, RunRecord
from qualor.workspace.versioning import opportunity_semantic_digest

FIXTURES = Path(__file__).parents[1] / "fixtures/workspace"
W01 = FIXTURES / "W01_DECISION_TO_DRAFT_PACK.json"
W02 = FIXTURES / "W02_PARTIAL_STALE_WATCH.json"
ORIGIN = "http://127.0.0.1:5173"
NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)


def fixture(path: Path) -> DecisionFixture:
    return DecisionFixture.model_validate_json(path.read_text(encoding="utf-8"))


def seed(
    database: Database,
    source: DecisionFixture,
    *,
    run_state="COMPLETED",
    termination_reason="SUFFICIENT_CRITICAL_EVIDENCE",
    provider_state=None,
    run_id=None,
):
    """Persist fixture inputs through the same repositories the product writes with."""
    decision = decide_fixture(source).selected_decision
    opportunity = source.opportunity
    identifier = run_id or f"run-{opportunity.id}"
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(source.founder)
        for entry in source.projects:
            store.projects.put_project(entry.project)
        store.opportunities.put_opportunity_version(
            opportunity, content_hash=opportunity_semantic_digest(opportunity)
        )
        for evidence in source.evidence:
            store.evidence.put_evidence(evidence, opportunity.id, opportunity.version)
        if decision is not None:
            store.decisions.put_decision(decision, founder_profile_id=source.founder.id)
        store.runs.create_run(
            RunRecord(
                schema_version="1",
                id=identifier,
                version=1,
                created_at=NOW,
                updated_at=NOW,
                provenance="DOCUMENTED",
                mode="FIXTURE",
                state=run_state,
                provider_state=provider_state,
                opportunity_id=opportunity.id,
                opportunity_version=opportunity.version,
                decision_id=decision.id if decision else None,
                decision_version=decision.version if decision else None,
                started_at=NOW,
                completed_at=NOW if run_state == "COMPLETED" else None,
                termination_reason=termination_reason,
            )
        )
        for event in ("OPPORTUNITY_DISCOVERED", "EVIDENCE_RECORDED", "DECISION_UPDATED"):
            store.runs.append_run_event(
                identifier,
                event_type=event,
                payload=RunEventPayload(count=1),
                mode="FIXTURE",
                occurred_at=NOW,
            )
    return decision


def reobserve(database: Database, source: DecisionFixture, *, run_id: str):
    """Observe the same opportunity again through the canonical observation boundary."""
    opportunity = source.opportunity
    outcome = WorkspaceLifecycle(database).persist_observation(opportunity)
    # Identical content is recognised as unchanged; no second version is written.
    assert outcome.status.value == "UNCHANGED", outcome
    assert outcome.created is False
    assert outcome.version == opportunity.version
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.runs.create_run(
            RunRecord(
                schema_version="1",
                id=run_id,
                version=1,
                created_at=NOW + timedelta(hours=2),
                updated_at=NOW + timedelta(hours=2),
                provenance="DOCUMENTED",
                mode="FIXTURE",
                state="COMPLETED",
                opportunity_id=opportunity.id,
                opportunity_version=opportunity.version,
                started_at=NOW + timedelta(hours=2),
                completed_at=NOW + timedelta(hours=2),
                termination_reason="SUFFICIENT_CRITICAL_EVIDENCE",
            )
        )


def make_app(database: Database, source: DecisionFixture, *, now=NOW):
    import qualor.api as api
    from qualor.settings import Settings

    decision = decide_fixture(source).selected_decision
    return api.create_app(
        Settings(database_path=database.path),
        actor_id=source.founder.id,
        policy_versions=decision.policy_versions if decision else None,
        mode="FIXTURE",
        clock=lambda: now,
    )


def client_for(app):
    return TestClient(app, client=("127.0.0.1", 12345), raise_server_exceptions=False)


def guard(client):
    session = client.get("/api/v1/session", headers={"Origin": ORIGIN})
    assert session.status_code == 200
    return {"Origin": ORIGIN, "X-QUALOR-Action-Token": session.json()["action_token"]}


@pytest.fixture
def w01(tmp_path):
    source = fixture(W01)
    database = Database(tmp_path / "workspace.db")
    seed(database, source)
    return database, source


def test_owned_fixture_reaches_an_immutable_application_pack_and_survives_restart(w01):
    """The complete judge flow: inputs in, deterministic authority out, durable afterwards."""
    database, source = w01
    opportunity_id = source.opportunity.id

    with client_for(make_app(database, source)) as client:
        headers = guard(client)

        inbox = client.get("/api/v1/inbox").json()
        assert inbox["profile_present"] is True
        assert [item["opportunity_id"] for item in inbox["items"]] == [opportunity_id]
        assert inbox["items"][0]["program_name"] == "AWS Agents for Humans"
        assert inbox["items"][0]["mode"] == "FIXTURE"

        workspace = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace").json()
        assert workspace["decision"]["recommendation"] == "APPLY"
        assert workspace["decision"]["eligibility"] == "PASS"
        assert workspace["decision"]["best_project"]["id"] == source.projects[0].project.id
        assert workspace["mode"] == "FIXTURE"
        assert (
            workspace["decision"]["strategy"]["semantics"] == "PRIORITIZATION_NOT_WIN_PROBABILITY"
        )

        evidence = client.get(f"/api/v1/opportunities/{opportunity_id}/evidence").json()
        assert evidence["proofs"], "Why/Proof must expose admitted source evidence"
        assert all(proof["original_url"] for proof in evidence["proofs"])

        activity = client.get("/api/v1/runs").json()
        assert [run["mode"] for run in activity["runs"]] == ["FIXTURE"]
        assert {event["event_type"] for event in activity["events"]} >= {"DECISION_UPDATED"}

        request = workspace["decision"]["primary_action"]["approval_request"]
        assert request is not None, "An APPLY decision must expose a version-bound request"
        pending = client.post(
            f"/api/v1/opportunities/{opportunity_id}/approvals", json=request, headers=headers
        ).json()
        assert pending["state"] == "PENDING_APPROVAL"
        assert pending["approved_snapshot"] == request

        confirmed = client.post(
            f"/api/v1/approvals/{pending['id']}/confirm",
            json={"expected_versions": request, "idempotency_key": "one-human-intent"},
            headers=headers,
        ).json()
        assert confirmed["state"] == "DRAFT_READY"
        assert confirmed["draft_job"]["id"] != pending["id"], "Drafting is a separate bounded job"
        pack_id = confirmed["pack_id"]

        pack = client.get(f"/api/v1/draft-packs/{pack_id}").json()
        assert [section["key"] for section in pack["sections"]] == [
            "SUBMISSION_SUMMARY",
            "PROJECT_FIT_NARRATIVE",
            "ELIGIBILITY_CHECKLIST",
            "REQUIRED_DELIVERABLES",
            "EVIDENCE_REFERENCES",
            "READINESS_GAPS",
            "SUGGESTED_APPLICATION_ANSWERS",
        ]
        assert pack["approval_id"] == pending["id"]
        assert pack["approved_snapshot"] == request
        assert pack["source_refs"] and pack["evidence_refs"]
        assert isinstance(pack["missing_fields"], list)
        original = pack

    # The database is closed with the client. Reopening must reconstruct the same truth.
    reopened = Database(database.path)
    with client_for(make_app(reopened, source, now=NOW + timedelta(hours=1))) as client:
        assert client.get(f"/api/v1/draft-packs/{pack_id}").json() == original
        again = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace").json()
        assert again["decision"]["recommendation"] == "APPLY"
        assert [item["opportunity_id"] for item in client.get("/api/v1/inbox").json()["items"]] == [
            opportunity_id
        ]


def test_a_critical_version_change_revokes_a_previously_valid_approval(w01):
    """Approval is bound to exact versions. The server, not the client, notices a change."""
    database, source = w01
    opportunity_id = source.opportunity.id
    with client_for(make_app(database, source)) as client:
        headers = guard(client)
        request = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace").json()[
            "decision"
        ]["primary_action"]["approval_request"]
        pending = client.post(
            f"/api/v1/opportunities/{opportunity_id}/approvals", json=request, headers=headers
        ).json()
        assert pending["state"] == "PENDING_APPROVAL"

        with database.transaction() as connection:
            project = source.projects[0].project
            WorkspaceStore(connection).projects.put_project(
                project.model_copy(update={"version": project.version + 1})
            )

        refused = client.post(
            f"/api/v1/approvals/{pending['id']}/confirm",
            json={"expected_versions": request, "idempotency_key": "one-human-intent"},
            headers=headers,
        )
        assert refused.status_code == 409, refused.text
        assert refused.json() == {"code": "VERSION_MISMATCH"}
        with database.transaction() as connection:
            assert connection.execute("SELECT count(*) FROM draft_packs").fetchone()[0] == 0


def test_a_failed_refresh_keeps_admitted_evidence_and_reports_it_as_stale(w01):
    """Stale is not deleted. The prior snapshot stays readable and stops being current."""
    database, source = w01
    opportunity_id = source.opportunity.id
    WorkspaceLifecycle(database).mark_refresh_failed(opportunity_id, NOW)

    with client_for(make_app(database, source)) as client:
        workspace = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace").json()
        assert workspace["freshness"] == "STALE"
        assert workspace["last_refresh_failed_at"] is not None
        assert workspace["product_state"]["state"] == "STALE_EVIDENCE"
        assert workspace["product_state"]["primary_action"] == "REFRESH_EVIDENCE"
        assert workspace["product_state"]["evidence_available"] is True
        assert workspace["product_state"]["approval_available"] is False

        evidence = client.get(f"/api/v1/opportunities/{opportunity_id}/evidence").json()
        assert evidence["proofs"], "A failed refresh must never delete admitted proof"


def test_an_unchanged_rerun_never_creates_a_second_inbox_opportunity(w01):
    """Re-observing the same opportunity keeps one identity and its first discovery."""
    database, source = w01
    with client_for(make_app(database, source)) as client:
        before = client.get("/api/v1/inbox").json()["items"]

    reobserve(database, source, run_id="run-repeat")

    with client_for(make_app(database, source)) as client:
        after = client.get("/api/v1/inbox").json()["items"]
    assert len(after) == len(before) == 1
    assert after[0]["opportunity_id"] == before[0]["opportunity_id"]
    assert after[0]["discovered_at"] == before[0]["discovered_at"]


def test_unresolved_eligibility_never_becomes_a_pass_or_an_approval(tmp_path):
    """W02 keeps its deterministic WATCH and refuses to invent completeness."""
    source = fixture(W02)
    database = Database(tmp_path / "workspace.db")
    seed(database, source, run_state="PARTIAL", termination_reason="NO_PROGRESS")
    opportunity_id = source.opportunity.id

    with client_for(make_app(database, source)) as client:
        headers = guard(client)
        workspace = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace").json()

        assert workspace["decision"]["eligibility"] != "PASS"
        assert workspace["decision"]["recommendation"] == "WATCH"
        assert workspace["run_state"] == "PARTIAL"
        assert workspace["mode"] == "FIXTURE"
        assert workspace["decision"]["primary_action"]["available"] is False
        assert workspace["product_state"]["approval_available"] is False

        request = workspace["decision"]["primary_action"]["approval_request"]
        if request is not None:
            refused = client.post(
                f"/api/v1/opportunities/{opportunity_id}/approvals", json=request, headers=headers
            )
            assert refused.status_code == 409, refused.text
        with database.transaction() as connection:
            assert connection.execute("SELECT count(*) FROM draft_packs").fetchone()[0] == 0


def test_a_partial_run_never_rewrites_a_deterministic_recommendation(w01):
    """PARTIAL describes the run. It does not restate what the decision engine decided."""
    database, source = w01
    opportunity_id = source.opportunity.id
    with database.transaction() as connection:
        WorkspaceStore(connection).runs.create_run(
            RunRecord(
                schema_version="1",
                id="run-partial",
                version=1,
                created_at=NOW + timedelta(minutes=5),
                updated_at=NOW + timedelta(minutes=5),
                provenance="DOCUMENTED",
                mode="FIXTURE",
                state="PARTIAL",
                opportunity_id=opportunity_id,
                opportunity_version=1,
                started_at=NOW + timedelta(minutes=5),
                termination_reason="MAX_STEPS",
            )
        )
    with client_for(make_app(database, source)) as client:
        workspace = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace").json()
        assert workspace["run_state"] == "PARTIAL"
        assert workspace["decision"]["recommendation"] == "APPLY"
        assert workspace["product_state"]["state"] == "PARTIAL_SOURCE_FAILURE"


def test_the_product_api_never_exposes_an_external_submission_boundary(w01):
    """The story ends at a prepared local pack. Nothing sends anything outward."""
    database, source = w01
    app = make_app(database, source)
    with client_for(app) as client:
        assert client.get("/api/v1/inbox").status_code == 200
        paths = {route.path for route in app.routes if hasattr(route, "path") and route.path}
        forbidden = ("submit", "send", "publish", "dispatch", "email", "webhook")
        assert not [p for p in paths if any(word in p.lower() for word in forbidden)]
