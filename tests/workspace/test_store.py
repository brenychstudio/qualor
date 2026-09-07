from pathlib import Path

import pytest

from qualor.decisions import DecisionFixture, decide_fixture
from qualor.persistence import Database
from qualor.workspace import RunRecord

FIXTURE = Path(__file__).parents[1] / "fixtures/decisions/D01_ELIGIBLE_HIGH_SCORE_READY_APPLY.json"


def test_store_composes_records_in_one_caller_owned_transaction_and_rolls_back(tmp_path):
    from qualor.workspace import WorkspaceStore

    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    database = Database(tmp_path / "workspace.db")
    with pytest.raises(RuntimeError, match="abort"):
        with database.transaction() as connection:
            store = WorkspaceStore(connection)
            store.profiles.put_founder(fixture.founder)
            store.projects.put_project(fixture.projects[0].project)
            raise RuntimeError("abort")

    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        assert store.profiles.get_founder(fixture.founder.id, 1) is None
        assert store.projects.get_project(fixture.projects[0].project.id, 1) is None


def test_store_reconstructs_linked_records_after_reopen(tmp_path):
    from qualor.workspace import WorkspaceStore

    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    decision = decide_fixture(fixture).selected_decision
    assert decision is not None
    metadata = {
        "schema_version": "1",
        "id": "run",
        "version": 1,
        "created_at": "2026-09-07T10:00:00Z",
        "updated_at": "2026-09-07T10:00:00Z",
        "provenance": "USER_ASSERTED",
    }
    run = RunRecord(
        **metadata,
        mode="FIXTURE",
        state="COMPLETED",
        opportunity_id=fixture.opportunity.id,
        opportunity_version=1,
        decision_id=decision.id,
        decision_version=1,
    )
    database = Database(tmp_path / "workspace.db")
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(fixture.founder)
        store.projects.put_project(fixture.projects[0].project)
        store.opportunities.put_opportunity_version(fixture.opportunity, content_hash="b" * 64)
        store.evidence.put_evidence(fixture.evidence[0], fixture.opportunity.id, 1)
        store.decisions.put_decision(decision, founder_profile_id=fixture.founder.id)
        store.runs.create_run(run)

    with database.transaction() as connection:
        linked = WorkspaceStore(connection).load_opportunity_workspace(fixture.opportunity.id, 1)
        assert linked.opportunity == fixture.opportunity
        assert linked.evidence == (fixture.evidence[0],)
        assert linked.decisions == (decision,)
        assert linked.runs == (run,)


def test_store_rejects_run_with_only_half_of_an_optional_link_pair(tmp_path):
    from qualor.workspace import WorkspaceStore

    run = RunRecord(
        schema_version="1",
        id="run",
        version=1,
        created_at="2026-09-07T10:00:00Z",
        updated_at="2026-09-07T10:00:00Z",
        provenance="USER_ASSERTED",
        mode="FIXTURE",
        state="CREATED",
        opportunity_id="opportunity",
    )
    with Database(tmp_path / "workspace.db").transaction() as connection:
        with pytest.raises(ValueError, match="opportunity link"):
            WorkspaceStore(connection).runs.create_run(run)


def test_run_event_mode_must_match_its_persisted_run(tmp_path):
    from qualor.persistence import InvalidReferenceError
    from qualor.workspace import WorkspaceStore

    run = RunRecord(
        schema_version="1",
        id="run",
        version=1,
        created_at="2026-09-07T10:00:00Z",
        updated_at="2026-09-07T10:00:00Z",
        provenance="USER_ASSERTED",
        mode="FIXTURE",
        state="CREATED",
    )
    with Database(tmp_path / "workspace.db").transaction() as connection:
        runs = WorkspaceStore(connection).runs
        runs.create_run(run)
        with pytest.raises(InvalidReferenceError, match="mode"):
            runs.append_run_event(
                run.id,
                event_type="STARTED",
                payload={},
                mode="REPLAY",
                occurred_at="2026-09-07T10:01:00Z",
            )
