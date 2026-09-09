"""Independent Task6 review regressions; every source is local persisted test data."""

import pytest
from test_workspace_api import NOW, ORIGIN, client_for, headers, make_app, seed

from qualor.workspace.models import RunRecord
from qualor.workspace.store import WorkspaceStore


@pytest.mark.parametrize(
    "run_state,refresh_failed,expected",
    [
        (None, False, "DISCOVERED"),
        ("RUNNING", False, "VERIFYING"),
        ("COMPLETED", False, "EVALUATED"),
        ("COMPLETED", True, "NEEDS_REVIEW"),
    ],
)
def test_inbox_public_presentation_state_survives_restart(
    tmp_path, run_state, refresh_failed, expected
):
    from qualor.persistence import Database
    from qualor.workspace.lifecycle import WorkspaceLifecycle
    from qualor.workspace.versioning import opportunity_semantic_digest

    database, fixture, decision = seed(tmp_path, state=run_state or "COMPLETED")
    if run_state is None:
        database = Database(tmp_path / "discovered.db")
        with database.transaction() as connection:
            WorkspaceStore(connection).opportunities.put_opportunity_version(
                fixture.opportunity,
                content_hash=opportunity_semantic_digest(fixture.opportunity),
            )
    if refresh_failed:
        WorkspaceLifecycle(database).mark_refresh_failed(fixture.opportunity.id, NOW)
    with client_for(make_app(database, fixture, decision)) as client:
        response = client.get("/api/v1/inbox")
        assert response.status_code == 200
        row = response.json()["items"][0]
        assert row["presentation_state"] == expected
        assert row["recommendation"] == ("APPLY" if run_state else None)
        workspace_response = client.get(
            f"/api/v1/opportunities/{fixture.opportunity.id}/workspace"
        )
        assert workspace_response.status_code == 200
        workspace = workspace_response.json()
        assert workspace["presentation_state"] == expected
        assert workspace["run_state"] == run_state
        assert workspace["mode"] == ("FIXTURE" if run_state else None)
        assert workspace["decision"]["recommendation"] == ("APPLY" if run_state else None)
        schemas = client.app.openapi()["components"]["schemas"]
        assert "presentation_state" in schemas["InboxItem"]["required"]
        assert schemas["InboxItem"]["properties"]["presentation_state"]["$ref"] == (
            "#/components/schemas/InboxPresentationState"
        )
        assert schemas["InboxPresentationState"]["enum"] == [
            "DISCOVERED", "VERIFYING", "EVALUATED", "NEEDS_REVIEW",
        ]
        assert {"presentation_state", "run_state", "mode"} <= set(
            schemas["OpportunityWorkspaceResponse"]["required"]
        )
    with client_for(make_app(Database(database.path), fixture, decision)) as client:
        assert client.get("/api/v1/inbox").json()["items"][0] == row
        assert client.get(
            f"/api/v1/opportunities/{fixture.opportunity.id}/workspace"
        ).json() == workspace


def test_direct_workspace_exposes_recorded_run_truth_outside_loaded_inbox_page(tmp_path):
    from qualor.domain import OpportunityRecord
    from qualor.workspace.versioning import opportunity_semantic_digest

    database, fixture, decision = seed(tmp_path)
    off_page = OpportunityRecord.model_validate({
        **fixture.opportunity.model_dump(), "program_name": "Persisted off-page opportunity",
    })
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.opportunities.put_opportunity_version(
            off_page, content_hash=opportunity_semantic_digest(off_page),
        )
        store.runs.create_run(RunRecord.model_validate({
            **store.runs.current("research").model_dump(), "id": "off-page-run",
            "opportunity_id": off_page.id, "mode": "LIVE", "state": "PARTIAL",
            "decision_id": None, "decision_version": None, "completed_at": None,
        }))
    # The local controller is configured for FIXTURE; that must not overwrite
    # the separately persisted run mode. No provider is invoked by this read.
    with client_for(make_app(database, fixture, decision)) as client:
        response = client.get(f"/api/v1/opportunities/{off_page.id}/workspace")
        assert response.status_code == 200
        workspace = response.json()
        assert workspace["presentation_state"] == "NEEDS_REVIEW"
        assert workspace["run_state"] == "PARTIAL"
        assert workspace["mode"] == "LIVE"
        assert workspace["decision"]["recommendation"] is None
        page = client.get("/api/v1/inbox?limit=1").json()
        assert page["page"]["has_more"]
        assert off_page.id not in {row["opportunity_id"] for row in page["items"]}


def approval_request(client, fixture):
    return client.get(f"/api/v1/opportunities/{fixture.opportunity.id}/workspace").json()[
        "decision"
    ]["primary_action"]


@pytest.mark.parametrize(
    "mode,official,actionable",
    [
        ("LIVE", False, False),
        ("LIVE", True, True),
        ("REPLAY", True, True),
    ],
)
def test_authority_uses_exact_persisted_source_run_mode(tmp_path, mode, official, actionable):
    database, fixture, decision = seed(tmp_path, mode=mode, official_evidence=official)
    app = make_app(database, fixture, decision)
    with client_for(app) as client:
        capability = approval_request(client, fixture)
        assert capability["available"] is actionable
        response = client.post(
            f"/api/v1/opportunities/{fixture.opportunity.id}/approvals",
            json=capability["approval_request"],
            headers=headers(client),
        )
        if not actionable:
            assert response.status_code == 409
            with database.transaction() as connection:
                assert connection.execute("SELECT count(*) FROM approvals").fetchone()[0] == 0
            return
        assert response.status_code == 200
        pending = response.json()
        with database.transaction() as connection:
            assert WorkspaceStore(connection).approvals.latest(pending["id"]).mode == mode
        result = client.post(
            f"/api/v1/approvals/{pending['id']}/confirm",
            json={
                "expected_versions": capability["approval_request"],
                "idempotency_key": "mode-intent",
            },
            headers=headers(client),
        )
        assert result.status_code == 200, result.text
        assert result.json()["draft_job"]["mode"] == mode
        assert result.json()["state"] == "DRAFT_READY"


@pytest.mark.parametrize("state", ["RUNNING", "PARTIAL", "FAILED", "BUDGET_STOPPED"])
def test_incomplete_source_run_cannot_create_new_approval(tmp_path, state):
    database, fixture, decision = seed(tmp_path, state=state)
    with client_for(make_app(database, fixture, decision)) as client:
        capability = approval_request(client, fixture)
        assert not capability["available"]
        assert capability["reason"] == "SOURCE_RUN_NOT_COMPLETED"
        result = client.post(
            f"/api/v1/opportunities/{fixture.opportunity.id}/approvals",
            json=capability["approval_request"],
            headers=headers(client),
        )
        assert result.status_code == 409
        assert result.json() == {"code": "SOURCE_RUN_NOT_COMPLETED"}


def test_ambiguous_completed_source_run_cannot_create_approval(tmp_path):
    from datetime import timedelta

    database, fixture, decision = seed(tmp_path)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        run = store.runs.current("research")
        store.runs.create_run(
            run.model_copy(
                update={
                    "id": "second",
                    "created_at": NOW + timedelta(seconds=1),
                    "updated_at": NOW + timedelta(seconds=1),
                    "completed_at": NOW + timedelta(seconds=1),
                }
            )
        )
    with client_for(
        make_app(database, fixture, decision, now=NOW + timedelta(seconds=2))
    ) as client:
        assert not approval_request(client, fixture)["available"]


def test_fractional_run_instants_order_chronologically(tmp_path):
    from datetime import timedelta

    database, fixture, decision = seed(tmp_path)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        run = store.runs.current("research")
        store.runs.create_run(
            run.model_copy(
                update={
                    "id": "fraction",
                    "created_at": NOW + timedelta(microseconds=500000),
                    "updated_at": NOW + timedelta(seconds=1),
                }
            )
        )
        assert [r.id for r in store.runs.list_current()] == ["research", "fraction"]
        assert [r.id for r in store.runs.list_for_opportunity(fixture.opportunity.id, 1)] == [
            "research",
            "fraction",
        ]


def test_global_activity_interleaves_events_but_single_run_retains_sequence(tmp_path):
    from datetime import timedelta

    database, fixture, decision = seed(tmp_path)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        run = store.runs.current("research")
        store.runs.create_run(run.model_copy(update={"id": "second"}))
        store.runs.append_run_event(
            "research",
            event_type="LATER",
            payload={},
            mode="FIXTURE",
            occurred_at=NOW + timedelta(minutes=3),
        )
        store.runs.append_run_event(
            "second",
            event_type="MIDDLE",
            payload={},
            mode="FIXTURE",
            occurred_at=NOW + timedelta(minutes=2),
        )
    with client_for(make_app(database, fixture, decision)) as client:
        events = client.get("/api/v1/runs").json()["events"]
        assert [e["event_type"] for e in events] == [
            "OPPORTUNITY_DISCOVERED",
            "DECISION_UPDATED",
            "MIDDLE",
            "LATER",
        ]
        assert [
            e["sequence"] for e in client.get("/api/v1/runs/research/events").json()["events"]
        ] == [1, 2, 3]


@pytest.mark.parametrize("readonly,status", [(False, 403), (True, 404)])
def test_allowed_origin_can_read_bounded_action_guard_errors(tmp_path, readonly, status):
    from qualor.persistence import Database

    with client_for(make_app(Database(tmp_path / "empty.db"), readonly=readonly)) as client:
        response = client.put("/api/v1/profile", json={}, headers={"Origin": ORIGIN})
        assert response.status_code == status
        assert response.headers.get("access-control-allow-origin") == ORIGIN
        evil = client.put("/api/v1/profile", json={}, headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in evil.headers


def test_evidence_sheet_has_all_four_deterministic_why_sections(tmp_path):
    database, fixture, decision = seed(tmp_path)
    with client_for(make_app(database, fixture, decision)) as client:
        sheet = client.get(f"/api/v1/opportunities/{fixture.opportunity.id}/evidence").json()
        assert sheet["eligibility"]["state"] == decision.eligibility_gate.state
        fit = sheet["project_fit"]
        assert fit["project"]["id"] == decision.project_id
        assert fit["factor_results"] == [
            f.model_dump(mode="json") for f in decision.project_match.factor_results
        ]
        assert fit["match_status"] == decision.project_match.match_status
        conflict = sheet["constraints_conflicts"]
        assert conflict["status"] == decision.conflict.status
        assert conflict["evidence_refs"] == list(decision.conflict.evidence_ids)
        assert conflict["founder_constraints"] == list(fixture.founder.constraints)
        rewards = sheet["reward_deadline"]
        assert rewards["rewards"] == [
            r.model_dump(mode="json") for r in fixture.opportunity.rewards
        ]
        assert rewards["deadline"]["timezone_status"] == "UTC"
        assert set(rewards["evidence_refs"]) == {
            e.id
            for e in fixture.evidence
            if e.normalized_field in {"DEADLINE", "REWARD_CONDITIONS"}
        }


@pytest.mark.parametrize(
    "mode,state",
    [
        ("FIXTURE", "FAILED"),
        ("REPLAY", "FAILED"),
        ("LIVE", "COMPLETED"),
        ("LIVE", "CREATED"),
        ("LIVE", "RUNNING"),
    ],
)
def test_disconnected_live_state_rejects_incompatible_record_and_repository(tmp_path, mode, state):
    from pydantic import ValidationError

    database, _, _ = seed(tmp_path)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        run = store.runs.current("research")
        bad = run.model_copy(
            update={
                "id": "invalid",
                "mode": mode,
                "state": state,
                "provider_state": "DISCONNECTED_LIVE_PROVIDER",
            }
        )
        with pytest.raises(ValidationError):
            RunRecord.model_validate_json(bad.model_dump_json(warnings=False))
        with pytest.raises(ValidationError):
            store.runs.create_run(bad)


def test_corrupt_disconnected_mode_cannot_be_returned_by_api(tmp_path):
    import json

    database, fixture, decision = seed(tmp_path)
    with database.transaction() as connection:
        run = WorkspaceStore(connection).runs.current("research")
        data = run.model_dump(mode="json")
        data["provider_state"] = "DISCONNECTED_LIVE_PROVIDER"
        connection.execute("UPDATE runs SET record_json=? WHERE id=?", (json.dumps(data), run.id))
    with client_for(make_app(database, fixture, decision)) as client:
        response = client.get("/api/v1/runs")
        assert response.status_code == 500
        assert response.json() == {"code": "INTERNAL_ERROR"}


def test_collection_pages_have_explicit_totals_and_keep_current_authority(tmp_path):
    from datetime import timedelta

    database, fixture, decision = seed(tmp_path)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        original = store.runs.current("research")
        for number in range(105):
            when = NOW - timedelta(days=1) + timedelta(microseconds=number)
            store.runs.create_run(
                original.model_copy(
                    update={
                        "id": f"old-{number:03}",
                        "created_at": when,
                        "updated_at": when,
                        "started_at": when,
                        "completed_at": when,
                        "decision_id": None,
                        "decision_version": None,
                    }
                )
            )
    with client_for(make_app(database, fixture, decision)) as client:
        first = client.get("/api/v1/runs?limit=2").json()
        assert len(first["runs"]) == 2
        assert first["runs_page"] == {"offset": 0, "limit": 2, "total": 106, "has_more": True}
        second = client.get("/api/v1/runs?limit=2&offset=2").json()
        assert {r["id"] for r in first["runs"]}.isdisjoint(r["id"] for r in second["runs"])
        workspace = client.get(
            f"/api/v1/opportunities/{fixture.opportunity.id}/workspace?limit=2"
        ).json()
        assert len(workspace["run_ids"]) == 2
        assert workspace["runs_page"]["total"] == 106
        assert workspace["decision"]["decision_id"] == decision.id
        assert workspace["decision"]["primary_action"]["available"]
        inbox = client.get("/api/v1/inbox?limit=2").json()
        assert inbox["page"]["total"] == 1


def test_evidence_and_per_run_events_page_without_silent_loss(tmp_path):
    from datetime import timedelta

    database, fixture, decision = seed(tmp_path)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        for number in range(5):
            store.runs.append_run_event(
                "research",
                event_type="MORE",
                payload={},
                mode="FIXTURE",
                occurred_at=NOW + timedelta(seconds=number),
            )
    with client_for(make_app(database, fixture, decision)) as client:
        events = client.get("/api/v1/runs/research/events?limit=2&offset=2").json()
        assert [e["sequence"] for e in events["events"]] == [3, 4]
        assert events["events_page"]["total"] == 7
        evidence = client.get(
            f"/api/v1/opportunities/{fixture.opportunity.id}/evidence?limit=2&proof_offset=2"
        ).json()
        assert len(evidence["proofs"]) == 2
        assert evidence["proofs_page"]["total"] == len(fixture.evidence)
        assert evidence["proofs_page"]["offset"] == 2
        assert evidence["claims_page"]["has_more"]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=bad"])
def test_collection_query_bounds_fail_closed(tmp_path, query):
    from qualor.persistence import Database

    with client_for(make_app(Database(tmp_path / "empty.db"))) as client:
        result = client.get("/api/v1/runs?" + query)
        assert result.status_code == 422
        assert result.json() == {"code": "INVALID_REQUEST"}


def test_public_collection_contracts_have_maximum_lengths():
    from qualor.workspace.read_models import (
        ActivityResponse,
        EvidenceSheetView,
        InboxResponse,
        OpportunityWorkspaceResponse,
    )

    for model, fields in (
        (ActivityResponse, ("runs", "events")),
        (InboxResponse, ("items",)),
        (EvidenceSheetView, ("claims", "proofs")),
        (OpportunityWorkspaceResponse, ("run_ids", "approvals")),
    ):
        schema = model.model_json_schema()
        for field in fields:
            assert schema["properties"][field].get("maxItems") == 100


def test_nonpaged_public_arrays_fail_with_explicit_bounded_error(tmp_path):
    database, fixture, decision = seed(tmp_path)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.runs.append_run_event(
            "research",
            event_type="TOO_MANY_REFS",
            payload={"source_ids": [f"s{i}" for i in range(101)]},
            mode="FIXTURE",
            occurred_at=NOW,
        )
    with client_for(make_app(database, fixture, decision)) as client:
        result = client.get("/api/v1/runs/research/events")
        assert result.status_code == 409
        assert result.json() == {"code": "READ_LIMIT_EXCEEDED"}


def test_claim_freshness_does_not_depend_on_visible_proof_page(tmp_path):
    database, fixture, decision = seed(tmp_path)
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    WorkspaceLifecycle(database).mark_refresh_failed(fixture.opportunity.id, NOW)
    with client_for(make_app(database, fixture, decision)) as client:
        sheet = client.get(
            f"/api/v1/opportunities/{fixture.opportunity.id}/evidence?limit=1&proof_offset=999"
        ).json()
        assert sheet["proofs"] == []
        assert sheet["claims"][0]["state"] == "STALE"
        assert sheet["proofs_page"]["total"] == len(fixture.evidence)


@pytest.mark.parametrize("tied_completed", [False, True])
def test_new_incomplete_run_retains_previous_decision_without_new_authority(
    tmp_path, tied_completed
):
    from datetime import timedelta

    database, fixture, decision = seed(tmp_path)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        run = store.runs.current("research")
        store.runs.create_run(
            run.model_copy(
                update={
                    "id": "new-research",
                    "state": "RUNNING",
                    "created_at": NOW + timedelta(seconds=1),
                    "updated_at": NOW + timedelta(seconds=1),
                    "started_at": NOW + timedelta(seconds=1),
                    "completed_at": None,
                    "decision_id": None,
                    "decision_version": None,
                }
            )
        )
        if tied_completed:
            store.runs.create_run(
                run.model_copy(
                    update={
                        "id": "a-tied",
                        "created_at": NOW + timedelta(seconds=1),
                        "updated_at": NOW + timedelta(seconds=1),
                        "completed_at": NOW + timedelta(seconds=1),
                        "decision_id": None,
                        "decision_version": None,
                    }
                )
            )
    with client_for(
        make_app(database, fixture, decision, now=NOW + timedelta(seconds=2))
    ) as client:
        workspace = client.get(f"/api/v1/opportunities/{fixture.opportunity.id}/workspace").json()
        assert workspace["decision"]["decision_id"] == decision.id
        assert workspace["decision"]["recommendation"] == "APPLY"
        capability = workspace["decision"]["primary_action"]
        assert not capability["available"]
        assert capability["reason"] == "SOURCE_RUN_NOT_COMPLETED"
        denied = client.post(
            f"/api/v1/opportunities/{fixture.opportunity.id}/approvals",
            json=capability["approval_request"],
            headers=headers(client),
        )
        assert denied.status_code == 409


def test_new_completed_run_without_decision_cannot_reauthorize_old_selection(tmp_path):
    from datetime import timedelta

    database, fixture, decision = seed(tmp_path)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        run = store.runs.current("research")
        later = NOW + timedelta(seconds=1)
        store.runs.create_run(
            run.model_copy(
                update={
                    "id": "new-completed",
                    "created_at": later,
                    "updated_at": later,
                    "completed_at": later,
                    "decision_id": None,
                    "decision_version": None,
                }
            )
        )
    with client_for(
        make_app(database, fixture, decision, now=NOW + timedelta(seconds=2))
    ) as client:
        capability = approval_request(client, fixture)
        assert not capability["available"]
        assert capability["reason"] == "GRAPH_MISMATCH"
