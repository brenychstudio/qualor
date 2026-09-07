import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from qualor.decisions import DecisionFixture, decide_fixture
from qualor.domain import OpportunityRecord
from qualor.persistence import Database
from qualor.workspace import ApprovalRecord, DraftJobRecord, DraftPack, RunRecord

FIXTURE = Path(__file__).parents[1] / "fixtures/decisions/D01_ELIGIBLE_HIGH_SCORE_READY_APPLY.json"


def records():
    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    decision = decide_fixture(fixture).selected_decision
    assert decision is not None
    metadata = {
        "schema_version": "1",
        "version": 1,
        "created_at": "2026-09-07T10:00:00Z",
        "updated_at": "2026-09-07T10:00:00Z",
        "provenance": "USER_ASSERTED",
    }
    run = RunRecord(**metadata, id="run", mode="FIXTURE", state="COMPLETED")
    approval = ApprovalRecord(
        **metadata,
        id="approval",
        actor_id="founder_synthetic",
        opportunity_id=fixture.opportunity.id,
        opportunity_hash="a" * 64,
        opportunity_version=1,
        founder_profile_id=fixture.founder.id,
        founder_profile_version=1,
        project_id=fixture.projects[0].project.id,
        project_version=1,
        decision_id=decision.id,
        decision_version=1,
        policy_versions=decision.policy_versions,
        action="GENERATE_DRAFT_PACK",
        state="APPROVED_FOR_PREPARATION",
        expires_at="2026-09-08T10:00:00Z",
        idempotency_key="approve-once",
    )
    job = DraftJobRecord(
        **metadata,
        id="job",
        approval_id=approval.id,
        mode="FIXTURE",
        state="COMPLETED",
        idempotency_key="draft-once",
    )
    pack = DraftPack(
        **metadata,
        id="pack",
        approval_id=approval.id,
        draft_job_id=job.id,
        opportunity_id=fixture.opportunity.id,
        opportunity_hash="a" * 64,
        opportunity_version=1,
        founder_profile_id=fixture.founder.id,
        founder_profile_version=1,
        project_id=fixture.projects[0].project.id,
        project_version=1,
        decision_id=decision.id,
        decision_version=1,
        policy_versions=decision.policy_versions,
        evidence_refs=(fixture.evidence[0].id,),
        source_refs=("official-rules",),
        missing_fields=(),
        authoring_facts=(
            {
                "key": "budget",
                "value": {"type": "DECIMAL", "value": "1.25"},
                "source": "EVIDENCE",
                "evidence_refs": (fixture.evidence[0].id,),
            },
        ),
        sections=({"key": "summary", "title": "Summary", "content": "Draft"},),
        generated_at="2026-09-07T10:00:00Z",
    )
    return fixture, decision, run, approval, job, pack


def persist_decision_dependencies(connection, fixture, decision):
    from qualor.persistence import (
        DecisionRepository,
        OpportunityRepository,
        ProfileRepository,
        ProjectRepository,
    )

    ProfileRepository(connection).put_founder(fixture.founder)
    ProjectRepository(connection).put_project(fixture.projects[0].project)
    OpportunityRepository(connection).put_opportunity_version(
        fixture.opportunity, content_hash="b" * 64
    )
    DecisionRepository(connection).put_decision(decision, founder_profile_id=fixture.founder.id)


def test_repositories_round_trip_all_ten_record_types(tmp_path):
    from qualor.persistence import (
        ApprovalRepository,
        DecisionRepository,
        DraftPackRepository,
        EvidenceRepository,
        OpportunityRepository,
        ProfileRepository,
        ProjectRepository,
        RunRepository,
    )

    fixture, decision, run, approval, job, pack = records()
    evidence = fixture.evidence[0]
    with Database(tmp_path / "workspace.db").transaction() as connection:
        profiles = ProfileRepository(connection)
        projects = ProjectRepository(connection)
        opportunities = OpportunityRepository(connection)
        evidence_repo = EvidenceRepository(connection)
        decisions = DecisionRepository(connection)
        runs = RunRepository(connection)
        approvals = ApprovalRepository(connection)
        drafts = DraftPackRepository(connection)

        profiles.put_founder(fixture.founder)
        projects.put_project(fixture.projects[0].project)
        opportunities.put_opportunity_version(fixture.opportunity, content_hash="b" * 64)
        evidence_repo.put_evidence(evidence, fixture.opportunity.id, 1)
        decisions.put_decision(decision, founder_profile_id=fixture.founder.id)
        runs.create_run(run)
        event = runs.append_run_event(
            run.id,
            event_type="SOURCE_FETCHED",
            payload={"status": "café", "estimated_cost_usd": "1.25", "source_ids": ("s1",)},
            mode="FIXTURE",
            occurred_at="2026-09-07T10:01:00Z",
        )
        approvals.put_approval(approval)
        drafts.put_draft_job(job)
        drafts.put_draft_pack(pack)

        assert profiles.get_founder(fixture.founder.id, 1) == fixture.founder
        assert (
            projects.get_project(fixture.projects[0].project.id, 1) == fixture.projects[0].project
        )
        assert (
            opportunities.get_opportunity_version(fixture.opportunity.id, 1) == fixture.opportunity
        )
        assert evidence_repo.get_evidence(evidence.id, 1) == evidence
        assert decisions.get_decision(decision.id, 1) == decision
        assert runs.get_run(run.id, 1) == run
        assert runs.list_run_events(run.id) == (event,)
        assert approvals.get_approval(approval.id, 1) == approval
        assert drafts.get_draft_job(job.id, 1) == job
        restored_pack = drafts.get_draft_pack(pack.id, 1)
        assert restored_pack == pack
        assert restored_pack.authoring_facts[0].value.value == Decimal("1.25")
        assert restored_pack.evidence_refs == (evidence.id,)


def test_immutable_identities_and_append_only_events_reject_conflicts(tmp_path):
    from qualor.persistence import DraftPackRepository, RepositoryConflictError, RunRepository

    fixture, decision, run, approval, job, pack = records()
    database = Database(tmp_path / "workspace.db")
    with database.transaction() as connection:
        runs = RunRepository(connection)
        runs.create_run(run)
        runs.append_run_event(
            run.id,
            event_type="STARTED",
            payload={},
            mode="FIXTURE",
            occurred_at="2026-09-07T10:01:00Z",
        )
        with pytest.raises(RepositoryConflictError):
            runs.append_run_event(
                run.id,
                sequence=1,
                event_type="DUPLICATE",
                payload={},
                mode="FIXTURE",
                occurred_at="2026-09-07T10:02:00Z",
            )

    # The database trigger proves mutation and deletion stay impossible through any caller.
    with database.transaction() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE run_events SET event_type='CHANGED' WHERE run_id='run'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM run_events WHERE run_id='run'")

    with database.transaction() as connection:
        persist_decision_dependencies(connection, fixture, decision)
        drafts = DraftPackRepository(connection)
        from qualor.persistence import ApprovalRepository

        ApprovalRepository(connection).put_approval(approval)
        drafts.put_draft_job(job)
        drafts.put_draft_pack(pack)
        with pytest.raises(RepositoryConflictError):
            drafts.put_draft_pack(pack)


def test_reads_revalidate_json_and_projected_columns(tmp_path):
    from qualor.persistence import CorruptRecordError, OpportunityRepository, RunRepository

    fixture, _, run, _, _, _ = records()
    database = Database(tmp_path / "workspace.db")
    with database.transaction() as connection:
        OpportunityRepository(connection).put_opportunity_version(
            fixture.opportunity, content_hash="b" * 64
        )
        RunRepository(connection).create_run(run)

    with database.transaction() as connection:
        connection.execute(
            "UPDATE opportunity_versions SET record_json=? WHERE id=? AND version=1",
            (
                json.dumps({**fixture.opportunity.model_dump(mode="json"), "organizer": ""}),
                fixture.opportunity.id,
            ),
        )
        with pytest.raises(CorruptRecordError, match="corrupt opportunity version"):
            OpportunityRepository(connection).get_opportunity_version(fixture.opportunity.id, 1)
        connection.execute("UPDATE runs SET mode='REPLAY' WHERE id='run'")
        with pytest.raises(CorruptRecordError, match="corrupt run"):
            RunRepository(connection).get_run("run", 1)


def test_missing_records_and_broken_references_fail_explicitly(tmp_path):
    from qualor.persistence import EvidenceRepository, InvalidReferenceError, ProfileRepository

    fixture, _, _, _, _, _ = records()
    with Database(tmp_path / "workspace.db").transaction() as connection:
        assert ProfileRepository(connection).get_founder("missing", 1) is None
        with pytest.raises(InvalidReferenceError, match="evidence opportunity reference"):
            EvidenceRepository(connection).put_evidence(fixture.evidence[0], "missing", 1)


def test_repository_conflicts_are_bounded_and_do_not_expose_record_payload(tmp_path):
    from qualor.persistence import ProfileRepository, RepositoryConflictError

    fixture, _, _, _, _, _ = records()
    with Database(tmp_path / "workspace.db").transaction() as connection:
        repo = ProfileRepository(connection)
        repo.put_founder(fixture.founder)
        with pytest.raises(RepositoryConflictError) as conflict:
            repo.put_founder(fixture.founder)
    assert fixture.founder.country_of_residence.value not in str(conflict.value)


def test_version_history_lists_old_and_new_records_without_overwrite(tmp_path):
    from qualor.persistence import DecisionRepository, OpportunityRepository

    fixture, decision, _, _, _, _ = records()
    opportunity_v2 = OpportunityRecord.model_validate(
        {
            **fixture.opportunity.model_dump(mode="json"),
            "version": 2,
            "updated_at": "2026-09-07T11:00:00Z",
            "deliverables": ["demo"],
        }
    )
    decision_v2 = type(decision).model_validate(
        {
            **decision.model_dump(mode="json"),
            "version": 2,
            "opportunity_version": 2,
            "updated_at": "2026-09-07T11:00:00Z",
        }
    )
    opportunity_v3 = OpportunityRecord.model_validate(
        {
            **fixture.opportunity.model_dump(mode="json"),
            "version": 3,
            "updated_at": "2026-09-07T12:00:00Z",
        }
    )
    distinct_decision = type(decision).model_validate(
        {
            **decision.model_dump(mode="json"),
            "id": "decision-distinct",
            "opportunity_version": 3,
            "updated_at": "2026-09-07T12:00:00Z",
        }
    )
    with Database(tmp_path / "workspace.db").transaction() as connection:
        persist_decision_dependencies(connection, fixture, decision)
        opportunities = OpportunityRepository(connection)
        decisions = DecisionRepository(connection)
        opportunities.put_opportunity_version(opportunity_v2, content_hash="c" * 64)
        opportunities.put_opportunity_version(opportunity_v3, content_hash="b" * 64)
        decisions.put_decision(decision_v2, founder_profile_id=fixture.founder.id)
        decisions.put_decision(distinct_decision, founder_profile_id=fixture.founder.id)
        assert opportunities.list_versions(fixture.opportunity.id) == (
            fixture.opportunity,
            opportunity_v2,
            opportunity_v3,
        )
        assert decisions.list_versions(decision.id) == (decision, decision_v2)
        assert decisions.get_decision(distinct_decision.id, 1) == distinct_decision


def test_auto_run_event_sequence_remains_ordered_across_transactions(tmp_path):
    from qualor.persistence import RunRepository

    _, _, run, _, _, _ = records()
    database = Database(tmp_path / "workspace.db")
    with database.transaction() as connection:
        repo = RunRepository(connection)
        repo.create_run(run)
        first = repo.append_run_event(
            run.id,
            event_type="STARTED",
            payload={},
            mode="FIXTURE",
            occurred_at="2026-09-07T10:01:00Z",
        )
    with database.transaction() as connection:
        repo = RunRepository(connection)
        second = repo.append_run_event(
            run.id,
            event_type="FINISHED",
            payload={},
            mode="FIXTURE",
            occurred_at="2026-09-07T10:02:00Z",
        )
        assert (first.sequence, second.sequence) == (1, 2)
        assert repo.list_run_events(run.id) == (first, second)


def test_explicit_run_event_sequence_cannot_bypass_next_sequence(tmp_path):
    from qualor.persistence import RepositoryConflictError, RunRepository

    _, _, run, _, _, _ = records()
    with Database(tmp_path / "workspace.db").transaction() as connection:
        repo = RunRepository(connection)
        repo.create_run(run)
        with pytest.raises(RepositoryConflictError, match="next sequence"):
            repo.append_run_event(
                run.id,
                sequence=10,
                event_type="STARTED",
                payload={},
                mode="FIXTURE",
                occurred_at="2026-09-07T10:01:00Z",
            )
        event = repo.append_run_event(
            run.id,
            sequence=1,
            event_type="STARTED",
            payload={},
            mode="FIXTURE",
            occurred_at="2026-09-07T10:01:00Z",
        )
        assert event.sequence == 1


def test_writes_require_an_active_caller_owned_transaction(tmp_path):
    from qualor.persistence import ProfileRepository, TransactionRequiredError

    fixture, _, _, _, _, _ = records()
    connection = Database(tmp_path / "workspace.db").connect()
    try:
        with pytest.raises(TransactionRequiredError, match="active caller-owned transaction"):
            ProfileRepository(connection).put_founder(fixture.founder)
        assert connection.execute("SELECT COUNT(*) FROM founder_profiles").fetchone()[0] == 0
    finally:
        connection.close()


def test_draft_pack_rejects_contradictory_job_approval_and_snapshot_graph(tmp_path):
    from qualor.persistence import ApprovalRepository, DraftPackRepository, InvalidReferenceError

    fixture, decision, _, approval, job, pack = records()
    approval_b = ApprovalRecord.model_validate(
        {
            **approval.model_dump(mode="json"),
            "id": "approval-b",
            "idempotency_key": "approve-b",
        }
    )
    contradictory = DraftPack.model_validate(
        {
            **pack.model_dump(mode="json"),
            "id": "pack-b",
            "approval_id": approval_b.id,
        }
    )
    wrong_snapshot = DraftPack.model_validate(
        {
            **pack.model_dump(mode="json"),
            "id": "pack-c",
            "opportunity_hash": "c" * 64,
        }
    )
    with Database(tmp_path / "workspace.db").transaction() as connection:
        persist_decision_dependencies(connection, fixture, decision)
        approvals = ApprovalRepository(connection)
        drafts = DraftPackRepository(connection)
        approvals.put_approval(approval)
        approvals.put_approval(approval_b)
        drafts.put_draft_job(job)
        with pytest.raises(InvalidReferenceError, match="job approval"):
            drafts.put_draft_pack(contradictory)
        with pytest.raises(InvalidReferenceError, match="approval snapshot"):
            drafts.put_draft_pack(wrong_snapshot)


def test_draft_pack_read_rejects_a_stored_contradictory_graph(tmp_path):
    from qualor.persistence import ApprovalRepository, DraftPackRepository, InvalidReferenceError

    fixture, decision, _, approval, job, pack = records()
    approval_b = ApprovalRecord.model_validate(
        {**approval.model_dump(mode="json"), "id": "approval-b", "idempotency_key": "approve-b"}
    )
    contradictory = DraftPack.model_validate(
        {**pack.model_dump(mode="json"), "id": "pack-b", "approval_id": approval_b.id}
    )
    with Database(tmp_path / "workspace.db").transaction() as connection:
        persist_decision_dependencies(connection, fixture, decision)
        approvals = ApprovalRepository(connection)
        approvals.put_approval(approval)
        approvals.put_approval(approval_b)
        drafts = DraftPackRepository(connection)
        drafts.put_draft_job(job)
        connection.execute(
            "INSERT INTO draft_packs(id, version, draft_job_id, draft_job_version, approval_id, "
            "approval_version, record_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                contradictory.id,
                contradictory.version,
                contradictory.draft_job_id,
                contradictory.draft_job_version,
                contradictory.approval_id,
                contradictory.approval_version,
                contradictory.model_dump_json(),
                contradictory.created_at.isoformat(),
            ),
        )
        with pytest.raises(InvalidReferenceError, match="job approval"):
            drafts.get_draft_pack(contradictory.id, 1)


def test_corrupt_referenced_draft_job_blocks_pack_write_and_read(tmp_path):
    from qualor.persistence import ApprovalRepository, CorruptRecordError, DraftPackRepository

    fixture, decision, _, approval, job, pack = records()
    approval_b = ApprovalRecord.model_validate(
        {**approval.model_dump(mode="json"), "id": "approval-b", "idempotency_key": "approve-b"}
    )
    divergent_job = DraftJobRecord.model_validate(
        {**job.model_dump(mode="json"), "approval_id": approval_b.id}
    )
    with Database(tmp_path / "workspace.db").transaction() as connection:
        persist_decision_dependencies(connection, fixture, decision)
        approvals = ApprovalRepository(connection)
        approvals.put_approval(approval)
        approvals.put_approval(approval_b)
        drafts = DraftPackRepository(connection)
        drafts.put_draft_job(job)
        connection.execute(
            "UPDATE draft_jobs SET record_json=? WHERE id=? AND version=?",
            (divergent_job.model_dump_json(), job.id, job.version),
        )
        with pytest.raises(CorruptRecordError, match="corrupt draft job"):
            drafts.put_draft_pack(pack)
        connection.execute(
            "INSERT INTO draft_packs(id, version, draft_job_id, draft_job_version, approval_id, "
            "approval_version, record_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                pack.id,
                pack.version,
                pack.draft_job_id,
                pack.draft_job_version,
                pack.approval_id,
                pack.approval_version,
                pack.model_dump_json(),
                pack.created_at.isoformat(),
            ),
        )
        with pytest.raises(CorruptRecordError, match="corrupt draft job"):
            drafts.get_draft_pack(pack.id, pack.version)


def test_revoke_approval_inserts_caller_decided_historical_version(tmp_path):
    from qualor.persistence import ApprovalRepository

    fixture, decision, _, approval, _, _ = records()
    revoked = ApprovalRecord.model_validate(
        {
            **approval.model_dump(mode="json"),
            "version": 2,
            "state": "REVOKED_APPROVAL",
            "idempotency_key": None,
            "revocation_reason": "CALLER_DECIDED_CHANGE",
            "updated_at": "2026-09-07T11:00:00Z",
        }
    )
    with Database(tmp_path / "workspace.db").transaction() as connection:
        persist_decision_dependencies(connection, fixture, decision)
        repo = ApprovalRepository(connection)
        repo.put_approval(approval)
        repo.revoke_approval(revoked)
        assert repo.get_approval(approval.id, 1) == approval
        assert repo.get_approval(approval.id, 2) == revoked
