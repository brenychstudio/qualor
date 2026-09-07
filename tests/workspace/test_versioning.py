from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from qualor.decisions import DecisionFixture
from qualor.domain import OpportunityRecord
from qualor.persistence import Database

FIXTURE = Path(__file__).parents[1] / "fixtures/decisions/D01_ELIGIBLE_HIGH_SCORE_READY_APPLY.json"


def fixture_record() -> OpportunityRecord:
    return DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8")).opportunity


def test_digest_ignores_snapshot_metadata_but_preserves_critical_meaning():
    from qualor.workspace.versioning import opportunity_semantic_digest

    original = fixture_record()
    cosmetic = OpportunityRecord.model_validate(
        {
            **original.model_dump(mode="json"),
            "version": 9,
            "created_at": "2026-09-07T12:00:00Z",
            "updated_at": "2026-09-07T12:00:00Z",
            "source_versions": ["new-page-hash"],
        }
    )
    changed = OpportunityRecord.model_validate(
        {**original.model_dump(mode="json"), "deadlines": ["2026-12-31"]}
    )

    assert opportunity_semantic_digest(original) == opportunity_semantic_digest(cosmetic)
    assert opportunity_semantic_digest(original) != opportunity_semantic_digest(changed)


def test_digest_decimal_encoding_is_exact_and_context_independent():
    from decimal import Decimal

    from qualor.domain import Reward
    from qualor.workspace.versioning import opportunity_semantic_digest

    original = fixture_record()

    def with_amount(amount: str) -> OpportunityRecord:
        reward = Reward(
            schema_version="1",
            id="reward",
            version=1,
            created_at="2026-09-01T00:00:00Z",
            updated_at="2026-09-01T00:00:00Z",
            provenance="DOCUMENTED",
            kind="CASH_PRIZE",
            amount={"currency": "USD", "amount": Decimal(amount)},
        )
        return OpportunityRecord.model_validate(
            {**original.model_dump(mode="json"), "rewards": [reward.model_dump(mode="json")]}
        )

    assert opportunity_semantic_digest(with_amount("1.0")) == opportunity_semantic_digest(
        with_amount("1.00")
    )
    assert opportunity_semantic_digest(
        with_amount("123456789012345678901234567890.1")
    ) != opportunity_semantic_digest(with_amount("123456789012345678901234567890.2"))
    assert opportunity_semantic_digest(with_amount("0")) == opportunity_semantic_digest(
        with_amount("-0.00")
    )


def test_digest_uses_normalized_identity_text_and_distinguishes_date_from_instant():
    from qualor.workspace.versioning import opportunity_semantic_digest

    original = fixture_record()
    identity_cosmetic = OpportunityRecord.model_validate(
        {
            **original.model_dump(mode="json"),
            "organizer": "  SYNTHETIC   example FOUNDATION ",
            "program_name": "OWNED deterministic TEST award",
        }
    )
    calendar = OpportunityRecord.model_validate(
        {**original.model_dump(mode="json"), "deadlines": ["2026-09-15"]}
    )
    instant = OpportunityRecord.model_validate(
        {**original.model_dump(mode="json"), "deadlines": ["2026-09-15T00:00:00Z"]}
    )

    assert opportunity_semantic_digest(original) == opportunity_semantic_digest(identity_cosmetic)
    assert opportunity_semantic_digest(calendar) != opportunity_semantic_digest(instant)


def test_unchanged_observation_reuses_version_and_critical_change_appends(tmp_path):
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    database = Database(tmp_path / "workspace.db")
    original = fixture_record()
    cosmetic = OpportunityRecord.model_validate(
        {
            **original.model_dump(mode="json"),
            "version": 77,
            "updated_at": "2026-09-07T11:00:00Z",
            "source_versions": ["cosmetic-snapshot"],
        }
    )
    changed = OpportunityRecord.model_validate(
        {
            **original.model_dump(mode="json"),
            "version": 1,
            "updated_at": "2026-09-07T12:00:00Z",
            "deliverables": [*original.deliverables, "Public demo"],
        }
    )

    first = WorkspaceLifecycle(database).persist_observation(original)
    same = WorkspaceLifecycle(database).persist_observation(cosmetic)
    second = WorkspaceLifecycle(database).persist_observation(changed)

    assert (first.version, first.created) == (1, True)
    assert (same.version, same.created) == (1, False)
    assert (second.version, second.created) == (2, True)
    assert first.status == "CHANGED"
    assert same.status == "UNCHANGED"
    assert second.changed_fields == ("deliverables",)
    with database.transaction() as connection:
        versions = (
            WorkspaceLifecycle(database)._store(connection).opportunities.list_versions(original.id)
        )
    assert [record.version for record in versions] == [1, 2]
    assert versions[0] == original
    assert versions[1].deliverables[-1] == "Public demo"


def test_a_b_a_observations_append_monotonic_history(tmp_path):
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    database = Database(tmp_path / "workspace.db")
    original = fixture_record()
    changed = OpportunityRecord.model_validate(
        {**original.model_dump(mode="json"), "deliverables": ["Changed"]}
    )
    service = WorkspaceLifecycle(database)

    assert service.persist_observation(original).version == 1
    assert service.persist_observation(changed).version == 2
    result = service.persist_observation(original)

    assert (result.version, result.created) == (3, True)


def test_concurrent_identical_observations_create_one_version(tmp_path):
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    database = Database(tmp_path / "workspace.db")
    database.connect().close()
    record = fixture_record()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            pool.map(lambda _: WorkspaceLifecycle(database).persist_observation(record), range(2))
        )

    assert sorted(result.created for result in results) == [False, True]
    assert {result.version for result in results} == {1}
    with database.transaction() as connection:
        assert (
            len(WorkspaceLifecycle._store(connection).opportunities.list_versions(record.id)) == 1
        )


def test_reconciliation_insert_rolls_back_when_database_aborts_after_insert(tmp_path):
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    database = Database(tmp_path / "workspace.db")
    database.connect().close()
    with database.transaction() as connection:
        connection.execute(
            "CREATE TRIGGER reject_observation AFTER INSERT ON opportunity_versions "
            "BEGIN SELECT RAISE(ABORT, 'forced lifecycle rollback'); END"
        )

    import pytest

    from qualor.persistence import RepositoryConflictError

    with pytest.raises(RepositoryConflictError):
        WorkspaceLifecycle(database).persist_observation(fixture_record())
    with database.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM opportunity_versions").fetchone()[0] == 0
