import runpy
from pathlib import Path

from qualor.decisions import DecisionFixture, decide_fixture
from qualor.persistence import Database

FIXTURE = Path(__file__).parents[1] / "fixtures/decisions/D01_ELIGIBLE_HIGH_SCORE_READY_APPLY.json"


def repository_records():
    module = runpy.run_path(str(Path(__file__).parents[1] / "persistence/test_repositories.py"))
    return module["records"]()


def test_failed_refresh_retains_evidence_and_is_stale_after_restart(tmp_path):
    from qualor.workspace import WorkspaceStore
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    database = Database(tmp_path / "workspace.db")
    service = WorkspaceLifecycle(database)
    service.persist_observation(fixture.opportunity)
    with database.transaction() as connection:
        WorkspaceStore(connection).evidence.put_evidence(
            fixture.evidence[0], fixture.opportunity.id, 1
        )

    failure = service.mark_refresh_failed(fixture.opportunity.id, "2026-09-07T12:00:00Z")
    assert (failure.status, failure.freshness) == ("REFRESH_FAILED", "STALE")
    reconstructed = WorkspaceLifecycle(Database(database.path)).reconstruct_workspace(
        fixture.opportunity.id, "2026-09-07T13:00:00Z"
    )

    assert reconstructed.freshness == "STALE"
    assert reconstructed.last_refresh_failed_at.isoformat() == "2026-09-07T12:00:00+00:00"
    assert reconstructed.current.evidence[0].retrieved_at == fixture.evidence[0].retrieved_at
    assert (
        reconstructed.current.evidence[0].supporting_excerpt
        == fixture.evidence[0].supporting_excerpt
    )


def test_no_evidence_refresh_failure_is_durable(tmp_path):
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    database = Database(tmp_path / "workspace.db")
    WorkspaceLifecycle(database).persist_observation(fixture.opportunity)
    WorkspaceLifecycle(database).mark_refresh_failed(fixture.opportunity.id, "2026-09-07T12:00:00Z")

    aggregate = WorkspaceLifecycle(Database(database.path)).reconstruct_workspace(
        fixture.opportunity.id, "2026-09-07T13:00:00Z"
    )
    assert aggregate.freshness == "STALE"
    assert aggregate.current.evidence == ()


def test_restart_reconstructs_current_and_historical_links(tmp_path):
    from qualor.domain import OpportunityRecord
    from qualor.workspace import WorkspaceStore
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    decision = decide_fixture(fixture).selected_decision
    assert decision is not None
    database = Database(tmp_path / "workspace.db")
    service = WorkspaceLifecycle(database)
    service.persist_observation(fixture.opportunity)
    changed = OpportunityRecord.model_validate(
        {**fixture.opportunity.model_dump(mode="json"), "deliverables": ["Changed"]}
    )
    service.persist_observation(changed)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(fixture.founder)
        store.projects.put_project(fixture.projects[0].project)
        store.evidence.put_evidence(fixture.evidence[0], fixture.opportunity.id, 1)
        store.decisions.put_decision(decision, founder_profile_id=fixture.founder.id)

    aggregate = WorkspaceLifecycle(Database(database.path)).reconstruct_workspace(
        fixture.opportunity.id, "2026-09-07T13:00:00Z"
    )

    assert aggregate.current.opportunity.version == 2
    assert [item.opportunity.version for item in aggregate.history] == [1, 2]
    assert aggregate.history[0].evidence == (fixture.evidence[0],)
    assert aggregate.history[0].decisions == (decision,)


def test_freshness_precedence_is_stale_then_unknown_then_fresh(tmp_path):
    from qualor.domain import EvidenceRecord
    from qualor.workspace import WorkspaceStore
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    database = Database(tmp_path / "workspace.db")
    WorkspaceLifecycle(database).persist_observation(fixture.opportunity)
    future = EvidenceRecord.model_validate(
        {
            **fixture.evidence[0].model_dump(mode="json"),
            "id": "future",
            "retrieved_at": "2026-09-08T00:00:00Z",
        }
    )
    stale = EvidenceRecord.model_validate(
        {
            **fixture.evidence[0].model_dump(mode="json"),
            "id": "stale",
            "retrieved_at": "2026-09-01T00:00:00Z",
        }
    )
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.evidence.put_evidence(future, fixture.opportunity.id, 1)
    aggregate = WorkspaceLifecycle(database).reconstruct_workspace(
        fixture.opportunity.id, "2026-09-07T13:00:00Z"
    )
    assert aggregate.freshness == "UNKNOWN"

    with database.transaction() as connection:
        WorkspaceStore(connection).evidence.put_evidence(stale, fixture.opportunity.id, 1)
    aggregate = WorkspaceLifecycle(database).reconstruct_workspace(
        fixture.opportunity.id, "2026-09-07T13:00:00Z"
    )
    assert aggregate.freshness == "STALE"

    fresh_database = Database(tmp_path / "fresh.db")
    WorkspaceLifecycle(fresh_database).persist_observation(fixture.opportunity)
    fresh = EvidenceRecord.model_validate(
        {
            **fixture.evidence[0].model_dump(mode="json"),
            "id": "fresh",
            "retrieved_at": "2026-09-07T12:30:00Z",
        }
    )
    with fresh_database.transaction() as connection:
        WorkspaceStore(connection).evidence.put_evidence(fresh, fixture.opportunity.id, 1)
    assert (
        WorkspaceLifecycle(fresh_database)
        .reconstruct_workspace(fixture.opportunity.id, "2026-09-07T13:00:00Z")
        .freshness
        == "FRESH"
    )


def test_failure_order_uses_parsed_instants_and_metadata_rerun_does_not_clear_stale(tmp_path):
    from qualor.domain import OpportunityRecord
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    database = Database(tmp_path / "workspace.db")
    service = WorkspaceLifecycle(database)
    service.persist_observation(fixture.opportunity)
    service.mark_refresh_failed(fixture.opportunity.id, "2026-09-07T12:00:00Z")
    service.mark_refresh_failed(fixture.opportunity.id, "2026-09-07T12:00:00.500000Z")
    metadata_only = OpportunityRecord.model_validate(
        {**fixture.opportunity.model_dump(mode="json"), "updated_at": "2026-09-07T12:30:00Z"}
    )
    assert service.persist_observation(metadata_only).status == "UNCHANGED"

    aggregate = service.reconstruct_workspace(fixture.opportunity.id, "2026-09-07T13:00:00Z")
    assert aggregate.freshness == "STALE"
    assert aggregate.last_refresh_failed_at.isoformat() == "2026-09-07T12:00:00.500000+00:00"


def test_restart_reconstructs_all_ten_record_types_and_ordered_events(tmp_path):
    from qualor.workspace import WorkspaceStore
    from qualor.workspace.lifecycle import WorkspaceLifecycle
    from qualor.workspace.versioning import opportunity_semantic_digest

    fixture, decision, run, approval, job, pack = repository_records()
    digest = opportunity_semantic_digest(fixture.opportunity)
    approval = approval.model_copy(update={"opportunity_hash": digest})
    pack = pack.model_copy(update={"opportunity_hash": digest})
    database = Database(tmp_path / "workspace.db")
    WorkspaceLifecycle(database).persist_observation(fixture.opportunity)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(fixture.founder)
        store.projects.put_project(fixture.projects[0].project)
        store.evidence.put_evidence(fixture.evidence[0], fixture.opportunity.id, 1)
        store.decisions.put_decision(decision, founder_profile_id=fixture.founder.id)
        linked_run = run.model_copy(
            update={
                "opportunity_id": fixture.opportunity.id,
                "opportunity_version": 1,
                "decision_id": decision.id,
                "decision_version": 1,
            }
        )
        store.runs.create_run(linked_run)
        first = store.runs.append_run_event(
            linked_run.id,
            event_type="FIRST",
            payload={},
            mode="FIXTURE",
            occurred_at="2026-09-07T10:01:00Z",
        )
        second = store.runs.append_run_event(
            linked_run.id,
            event_type="SECOND",
            payload={},
            mode="FIXTURE",
            occurred_at="2026-09-07T10:02:00Z",
        )
        store.approvals.put_approval(approval)
        store.drafts.put_draft_job(job)
        store.drafts.put_draft_pack(pack)

    aggregate = WorkspaceLifecycle(Database(database.path)).reconstruct_workspace(
        fixture.opportunity.id, "2026-09-07T13:00:00Z"
    )
    assert aggregate.founder_profiles == (fixture.founder,)
    assert aggregate.project_profiles == (fixture.projects[0].project,)
    assert aggregate.approvals == (approval,)
    assert aggregate.draft_jobs == (job,)
    assert aggregate.draft_packs == (pack,)
    assert aggregate.run_events == (first, second)
    assert aggregate.approval_versions[0].status == "VERSION_MATCH_ONLY"


def test_reconstruction_rejects_decision_snapshot_mismatch_and_old_a_b_a_approval(tmp_path):
    import pytest

    from qualor.domain import OpportunityRecord
    from qualor.persistence import InvalidReferenceError
    from qualor.workspace import WorkspaceStore
    from qualor.workspace.lifecycle import WorkspaceLifecycle
    from qualor.workspace.versioning import opportunity_semantic_digest

    fixture, decision, _, approval, _, _ = repository_records()
    database = Database(tmp_path / "workspace.db")
    service = WorkspaceLifecycle(database)
    service.persist_observation(fixture.opportunity)
    changed = OpportunityRecord.model_validate(
        {**fixture.opportunity.model_dump(mode="json"), "deliverables": ["B"]}
    )
    service.persist_observation(changed)
    returned = service.persist_observation(fixture.opportunity)
    old_approval = approval.model_copy(
        update={"opportunity_hash": opportunity_semantic_digest(fixture.opportunity)}
    )
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(fixture.founder)
        store.projects.put_project(fixture.projects[0].project)
        store.decisions.put_decision(decision, founder_profile_id=fixture.founder.id)
        store.approvals.put_approval(old_approval)
    aggregate = service.reconstruct_workspace(fixture.opportunity.id, "2026-09-07T13:00:00Z")
    assert returned.version == 3
    assert aggregate.approval_versions[0].status == "VERSION_MISMATCH"

    mismatched = old_approval.model_copy(
        update={
            "id": "approval-current",
            "opportunity_version": 3,
            "opportunity_hash": returned.digest,
            "idempotency_key": "approval-current",
        }
    )
    with database.transaction() as connection:
        WorkspaceStore(connection).approvals.put_approval(mismatched)
    with pytest.raises(InvalidReferenceError, match="decision snapshot"):
        service.reconstruct_workspace(fixture.opportunity.id, "2026-09-07T13:00:00Z")


def test_reconstruction_validates_decision_links_without_an_approval(tmp_path):
    import sqlite3

    import pytest

    from qualor.persistence import InvalidReferenceError
    from qualor.workspace import WorkspaceStore
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    decision = decide_fixture(fixture).selected_decision
    assert decision is not None
    database = Database(tmp_path / "workspace.db")
    WorkspaceLifecycle(database).persist_observation(fixture.opportunity)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(fixture.founder)
        store.projects.put_project(fixture.projects[0].project)
        store.decisions.put_decision(decision, founder_profile_id=fixture.founder.id)

    connection = sqlite3.connect(database.path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DELETE FROM founder_profiles WHERE id=?", (fixture.founder.id,))
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(InvalidReferenceError, match="Decision snapshot"):
        WorkspaceLifecycle(database).reconstruct_workspace(
            fixture.opportunity.id, "2026-09-07T13:00:00Z"
        )


def test_reconstruction_rejects_approval_with_different_founder_at_same_version(tmp_path):
    import pytest

    from qualor.persistence import InvalidReferenceError
    from qualor.workspace import WorkspaceStore
    from qualor.workspace.lifecycle import WorkspaceLifecycle
    from qualor.workspace.versioning import opportunity_semantic_digest

    fixture, decision, _, approval, _, _ = repository_records()
    founder_b = fixture.founder.model_copy(update={"id": "founder-b"})
    mismatched = approval.model_copy(
        update={
            "founder_profile_id": founder_b.id,
            "opportunity_hash": opportunity_semantic_digest(fixture.opportunity),
        }
    )
    database = Database(tmp_path / "workspace.db")
    WorkspaceLifecycle(database).persist_observation(fixture.opportunity)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(fixture.founder)
        store.profiles.put_founder(founder_b)
        store.projects.put_project(fixture.projects[0].project)
        store.decisions.put_decision(decision, founder_profile_id=fixture.founder.id)
        store.approvals.put_approval(mismatched)

    with pytest.raises(InvalidReferenceError, match="decision snapshot"):
        WorkspaceLifecycle(database).reconstruct_workspace(
            fixture.opportunity.id, "2026-09-07T13:00:00Z"
        )
