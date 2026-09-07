from datetime import datetime

import pytest
from pydantic import ValidationError


def record_metadata(record_id: str = "record") -> dict[str, object]:
    return {
        "schema_version": "1",
        "id": record_id,
        "version": 1,
        "created_at": "2026-09-07T10:00:00Z",
        "updated_at": "2026-09-07T10:00:00Z",
        "provenance": "USER_ASSERTED",
    }


def policy_versions() -> dict[str, int]:
    return {
        "eligibility": 1,
        "matching": 1,
        "effort": 1,
        "conflicts": 1,
        "strategy": 1,
        "decisions": 1,
    }


@pytest.mark.parametrize("state", ["QUEUED", "SUCCEEDED", "UNKNOWN"])
def test_run_record_rejects_noncanonical_states(state):
    from qualor.workspace import RunRecord

    with pytest.raises(ValidationError):
        RunRecord(**record_metadata("run"), mode="FIXTURE", state=state)


@pytest.mark.parametrize("state", ["APPROVED", "EXPIRED", "CONSUMED"])
def test_approval_record_rejects_noncanonical_states(state):
    from qualor.workspace import ApprovalRecord

    with pytest.raises(ValidationError):
        ApprovalRecord(
            **record_metadata("approval"),
            actor_id="founder",
            opportunity_id="opportunity",
            opportunity_hash="a" * 64,
            opportunity_version=1,
            founder_profile_id="founder",
            founder_profile_version=1,
            project_id="project",
            project_version=1,
            decision_id="decision",
            decision_version=1,
            policy_versions=policy_versions(),
            action="GENERATE_DRAFT_PACK",
            state=state,
            expires_at="2026-09-08T10:00:00Z",
        )


@pytest.mark.parametrize("state", ["PENDING", "SUCCEEDED", "DRAFT_READY"])
def test_draft_job_rejects_noncanonical_states(state):
    from qualor.workspace import DraftJobRecord

    with pytest.raises(ValidationError):
        DraftJobRecord(
            **record_metadata("job"),
            approval_id="approval",
            mode="FIXTURE",
            state=state,
            idempotency_key="draft-request",
        )


@pytest.mark.parametrize("model_name", ["run", "event", "approval", "job", "pack"])
def test_workspace_records_reject_naive_timestamps(model_name):
    from qualor.workspace import (
        ApprovalRecord,
        DraftJobRecord,
        DraftPack,
        RunEvent,
        RunRecord,
    )

    naive = datetime(2026, 9, 7, 10)
    factories = {
        "run": lambda: RunRecord(
            **{**record_metadata("run"), "created_at": naive}, mode="FIXTURE", state="CREATED"
        ),
        "event": lambda: RunEvent(
            run_id="run",
            sequence=1,
            event_type="RUN_STARTED",
            payload={},
            mode="FIXTURE",
            occurred_at=naive,
        ),
        "approval": lambda: ApprovalRecord(
            **record_metadata("approval"),
            actor_id="founder",
            opportunity_id="opportunity",
            opportunity_hash="a" * 64,
            opportunity_version=1,
            founder_profile_id="founder",
            founder_profile_version=1,
            project_id="project",
            project_version=1,
            decision_id="decision",
            decision_version=1,
            policy_versions=policy_versions(),
            action="GENERATE_DRAFT_PACK",
            state="PENDING_APPROVAL",
            expires_at=naive,
        ),
        "job": lambda: DraftJobRecord(
            **record_metadata("job"),
            approval_id="approval",
            mode="FIXTURE",
            state="CREATED",
            idempotency_key="draft-request",
            started_at=naive,
        ),
        "pack": lambda: DraftPack(
            **record_metadata("pack"),
            approval_id="approval",
            draft_job_id="job",
            opportunity_id="opportunity",
            opportunity_hash="a" * 64,
            opportunity_version=1,
            founder_profile_id="founder",
            founder_profile_version=1,
            project_id="project",
            project_version=1,
            decision_id="decision",
            decision_version=1,
            policy_versions=policy_versions(),
            evidence_refs=(),
            source_refs=(),
            missing_fields=(),
            authoring_facts=(),
            sections=(),
            generated_at=naive,
        ),
    }

    with pytest.raises(ValidationError):
        factories[model_name]()


def test_run_event_payload_is_bounded_and_judge_safe():
    from qualor.workspace import RunEvent

    base = dict(
        run_id="run",
        sequence=1,
        event_type="SOURCE_FETCHED",
        mode="FIXTURE",
        occurred_at="2026-09-07T10:00:00Z",
    )
    with pytest.raises(ValidationError):
        RunEvent(**base, payload={"raw_source_page": "private"})
    with pytest.raises(ValidationError, match="exceeds 4096 bytes"):
        RunEvent(**base, payload={"source_ids": ("x" * 4096,)})
    with pytest.raises(ValidationError):
        RunEvent(**base, payload={"invented_field": "looks safe but is not typed"})


def test_draft_pack_is_immutable():
    from qualor.workspace import DraftPack

    pack = DraftPack(
        **record_metadata("pack"),
        approval_id="approval",
        draft_job_id="job",
        opportunity_id="opportunity",
        opportunity_hash="a" * 64,
        opportunity_version=1,
        founder_profile_id="founder",
        founder_profile_version=1,
        project_id="project",
        project_version=1,
        decision_id="decision",
        decision_version=1,
        policy_versions=policy_versions(),
        evidence_refs=("evidence",),
        source_refs=("source",),
        missing_fields=(),
        authoring_facts=(
            {
                "key": "project_name",
                "value": {"type": "STRING", "value": "QUALOR"},
                "source": "PROJECT_PROFILE",
            },
        ),
        sections=({"key": "summary", "title": "Summary", "content": "Draft"},),
        generated_at="2026-09-07T10:00:00Z",
    )
    with pytest.raises(ValidationError):
        pack.version = 2
    with pytest.raises(ValidationError):
        pack.authoring_facts[0].value.value = "changed"


def test_draft_pack_authoring_fact_types_survive_json_round_trip():
    from decimal import Decimal

    from qualor.workspace import DraftPack

    facts = (
        {"key": "decimal", "value": {"type": "DECIMAL", "value": "1.25"}, "source": "EVIDENCE"},
        {"key": "string", "value": {"type": "STRING", "value": "1.25"}, "source": "EVIDENCE"},
        {"key": "integer", "value": {"type": "INTEGER", "value": 7}, "source": "EVIDENCE"},
        {"key": "boolean", "value": {"type": "BOOLEAN", "value": True}, "source": "EVIDENCE"},
        {
            "key": "strings",
            "value": {"type": "STRINGS", "value": ("one", "two")},
            "source": "EVIDENCE",
        },
    )
    pack = DraftPack(
        **record_metadata("pack"),
        approval_id="approval",
        draft_job_id="job",
        opportunity_id="opportunity",
        opportunity_hash="a" * 64,
        opportunity_version=1,
        founder_profile_id="founder",
        founder_profile_version=1,
        project_id="project",
        project_version=1,
        decision_id="decision",
        decision_version=1,
        policy_versions=policy_versions(),
        evidence_refs=(),
        source_refs=(),
        missing_fields=(),
        authoring_facts=facts,
        sections=(),
        generated_at="2026-09-07T10:00:00Z",
    )

    restored = DraftPack.model_validate_json(pack.model_dump_json())
    assert restored == pack
    assert restored.authoring_facts[0].value.value == Decimal("1.25")
    assert restored.authoring_facts[1].value.value == "1.25"
    assert restored.authoring_facts[2].value.value == 7
    assert restored.authoring_facts[3].value.value is True
    assert restored.authoring_facts[4].value.value == ("one", "two")


def test_workspace_records_round_trip_as_json():
    from qualor.workspace import RunEvent, RunRecord

    run = RunRecord(**record_metadata("run"), mode="REPLAY", state="PARTIAL")
    event = RunEvent(
        run_id="run",
        sequence=1,
        event_type="SOURCE_FETCHED",
        payload={"reason_code": "OFFICIAL_SOURCE", "count": 1},
        mode="REPLAY",
        occurred_at="2026-09-07T10:00:00Z",
    )
    assert RunRecord.model_validate_json(run.model_dump_json()) == run
    assert RunEvent.model_validate_json(event.model_dump_json()) == event


def test_settings_database_default_has_no_filesystem_side_effect(tmp_path, monkeypatch):
    from qualor.settings import Settings

    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)
    assert settings.database_path.as_posix() == ".qualor/local/qualor.db"
    assert not (tmp_path / ".qualor").exists()
