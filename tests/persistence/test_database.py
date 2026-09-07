import sqlite3

import pytest
from pydantic import ValidationError


def test_new_database_migrates_once_and_reopen_is_idempotent(tmp_path):
    from qualor.persistence import Database

    database = Database(tmp_path / "workspace.db")
    first = database.connect()
    try:
        assert [row[0] for row in first.execute("SELECT version FROM schema_migrations")] == [1]
        expected_tables = {
            "approvals",
            "decisions",
            "draft_jobs",
            "draft_packs",
            "evidence",
            "founder_profiles",
            "opportunity_versions",
            "project_profiles",
            "run_events",
            "runs",
            "schema_migrations",
        }
        actual_tables = {
            row[0]
            for row in first.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert actual_tables == expected_tables
    finally:
        first.close()

    reopened = database.connect()
    try:
        assert reopened.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
        assert reopened.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert reopened.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert reopened.row_factory is sqlite3.Row
    finally:
        reopened.close()


def test_future_and_gapped_schema_histories_fail_closed(tmp_path):
    from qualor.persistence import Database, UnsupportedSchemaError

    future_path = tmp_path / "future.db"
    connection = sqlite3.connect(future_path)
    connection.execute(
        "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    connection.execute("INSERT INTO schema_migrations VALUES (2, '2026-09-07T00:00:00Z')")
    connection.commit()
    connection.close()

    with pytest.raises(UnsupportedSchemaError):
        Database(future_path).connect()

    gap_path = tmp_path / "gap.db"
    connection = sqlite3.connect(gap_path)
    connection.execute(
        "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    connection.execute("INSERT INTO schema_migrations VALUES (0, '2026-09-07T00:00:00Z')")
    connection.commit()
    connection.close()

    with pytest.raises(UnsupportedSchemaError):
        Database(gap_path).connect()

    check = sqlite3.connect(gap_path)
    try:
        assert check.execute("SELECT version FROM schema_migrations").fetchall() == [(0,)]
        assert check.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='runs'"
        ).fetchone()[0] == 0
    finally:
        check.close()


def test_foreign_keys_are_active_and_transaction_rolls_back_every_exception(tmp_path):
    from qualor.persistence import Database

    database = Database(tmp_path / "workspace.db")
    connection = database.connect()
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_events"
                "(run_id, sequence, event_type, payload_json, mode, occurred_at) "
                "VALUES ('missing', 1, 'STARTED', '{}', 'FIXTURE', '2026-09-07T00:00:00Z')"
            )
    finally:
        connection.close()

    with pytest.raises(BaseException, match="abort"):
        with database.transaction() as transaction:
            transaction.execute(
                "INSERT INTO founder_profiles(id, version, record_json, created_at) "
                "VALUES ('founder', 1, '{}', '2026-09-07T00:00:00Z')"
            )
            transaction.execute(
                "INSERT INTO project_profiles(id, version, record_json, created_at) "
                "VALUES ('project', 1, '{}', '2026-09-07T00:00:00Z')"
            )
            raise BaseException("abort")

    reopened = database.connect()
    try:
        assert reopened.execute("SELECT COUNT(*) FROM founder_profiles").fetchone()[0] == 0
        assert reopened.execute("SELECT COUNT(*) FROM project_profiles").fetchone()[0] == 0
    finally:
        reopened.close()


def test_run_events_are_append_only(tmp_path):
    from qualor.persistence import Database

    database = Database(tmp_path / "workspace.db")
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO runs(id, version, record_json, mode, state, created_at, updated_at) "
            "VALUES ('run', 1, '{}', 'FIXTURE', 'CREATED', "
            "'2026-09-07T00:00:00Z', '2026-09-07T00:00:00Z')"
        )
        connection.execute(
            "INSERT INTO run_events(run_id, sequence, event_type, payload_json, mode, occurred_at) "
            "VALUES ('run', 1, 'STARTED', '{}', 'FIXTURE', '2026-09-07T00:00:00Z')"
        )

    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction() as connection:
            connection.execute("UPDATE run_events SET event_type='CHANGED' WHERE run_id='run'")
    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction() as connection:
            connection.execute("DELETE FROM run_events WHERE run_id='run'")


def test_run_event_schema_bounds_payload_by_utf8_bytes(tmp_path):
    from qualor.persistence import Database

    database = Database(tmp_path / "workspace.db")
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO runs(id, version, record_json, mode, state, created_at, updated_at) "
            "VALUES ('run', 1, '{}', 'FIXTURE', 'CREATED', "
            "'2026-09-07T00:00:00Z', '2026-09-07T00:00:00Z')"
        )
        oversized_utf8 = '{"status":"' + ("é" * 3000) + '"}'
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_events"
                "(run_id, sequence, event_type, payload_json, mode, occurred_at) "
                "VALUES ('run', 1, 'STARTED', ?, 'FIXTURE', '2026-09-07T00:00:00Z')",
                (oversized_utf8,),
            )


def test_committed_records_survive_connection_close(tmp_path):
    from qualor.persistence import Database

    database = Database(tmp_path / "workspace.db")
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO founder_profiles(id, version, record_json, created_at) "
            "VALUES ('founder', 1, '{\"id\":\"founder\"}', '2026-09-07T00:00:00Z')"
        )

    reopened = database.connect()
    try:
        row = reopened.execute(
            "SELECT id, version, record_json FROM founder_profiles WHERE id='founder'"
        ).fetchone()
        assert dict(row) == {"id": "founder", "version": 1, "record_json": '{"id":"founder"}'}
    finally:
        reopened.close()


def test_failed_migration_rolls_back_schema_and_history(tmp_path, monkeypatch):
    import qualor.persistence.migrations as migration_module
    from qualor.persistence import Database

    broken = migration_module.MIGRATION_1 + ("CREATE TABLE broken (",)
    monkeypatch.setattr(migration_module, "MIGRATIONS", (broken,))

    with pytest.raises(sqlite3.OperationalError):
        Database(tmp_path / "broken.db").connect()

    connection = sqlite3.connect(tmp_path / "broken.db")
    try:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name != 'schema_migrations'"
            )
        }
        assert tables == set()
    finally:
        connection.close()


def test_version_history_does_not_deduplicate_distinct_record_ids(tmp_path):
    from qualor.persistence import Database

    database = Database(tmp_path / "workspace.db")
    with database.transaction() as connection:
        connection.executemany(
            "INSERT INTO founder_profiles(id, version, record_json, created_at) "
            "VALUES (?, ?, '{}', ?)",
            [("founder", 1, "2026-09-07T00:00:00Z")],
        )
        connection.execute(
            "INSERT INTO project_profiles(id, version, record_json, created_at) "
            "VALUES ('project', 1, '{}', '2026-09-07T00:00:00Z')"
        )
        for version, content_hash in [(1, "same"), (2, "changed"), (3, "same")]:
            connection.execute(
                "INSERT INTO opportunity_versions"
                "(id, version, record_json, content_hash, created_at) "
                "VALUES ('opportunity', ?, '{}', ?, '2026-09-07T00:00:00Z')",
                (version, content_hash),
            )
        for decision_id in ("decision-a", "decision-b"):
            connection.execute(
                "INSERT INTO decisions(id, version, opportunity_id, opportunity_version, "
                "founder_profile_id, founder_profile_version, project_id, project_version, "
                "record_json, created_at) VALUES (?, 1, 'opportunity', 1, 'founder', 1, "
                "'project', 1, '{}', '2026-09-07T00:00:00Z')",
                (decision_id,),
            )

    connection = database.connect()
    try:
        assert connection.execute("SELECT COUNT(*) FROM opportunity_versions").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 2
    finally:
        connection.close()


def test_draft_job_requires_schema_compatible_idempotency_key(tmp_path):
    from qualor.persistence import Database
    from qualor.workspace import DraftJobRecord

    with pytest.raises(ValidationError) as missing:
        DraftJobRecord(
            **record_metadata_for_sql("job"),
            approval_id="approval",
            mode="FIXTURE",
            state="CREATED",
        )
    assert missing.value.errors()[0]["loc"] == ("idempotency_key",)

    job = DraftJobRecord(
        **record_metadata_for_sql("job"),
        approval_id="approval",
        mode="FIXTURE",
        state="CREATED",
        idempotency_key="draft-request",
    )
    connection = Database(tmp_path / "workspace.db").connect()
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "INSERT INTO draft_jobs(id, version, approval_id, approval_version, record_json, "
            "state, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job.id,
                job.version,
                job.approval_id,
                job.approval_version,
                job.model_dump_json(),
                job.state,
                job.idempotency_key,
                job.created_at.isoformat(),
            ),
        )
        assert connection.execute("SELECT idempotency_key FROM draft_jobs").fetchone()[0] == (
            "draft-request"
        )
    finally:
        connection.close()


def test_commit_exception_rolls_back_and_closes_connection(tmp_path, monkeypatch):
    from qualor.persistence import Database

    calls: list[str] = []

    class FailingCommitConnection:
        def execute(self, statement):
            calls.append(statement)

        def commit(self):
            calls.append("commit")
            raise RuntimeError("commit failed")

        def rollback(self):
            calls.append("rollback")

        def close(self):
            calls.append("close")

    database = Database(tmp_path / "workspace.db")
    monkeypatch.setattr(database, "connect", lambda: FailingCommitConnection())

    with pytest.raises(RuntimeError, match="commit failed"):
        with database.transaction():
            pass
    assert calls == ["BEGIN", "commit", "rollback", "close"]


def record_metadata_for_sql(record_id: str) -> dict[str, object]:
    return {
        "schema_version": "1",
        "id": record_id,
        "version": 1,
        "created_at": "2026-09-07T10:00:00Z",
        "updated_at": "2026-09-07T10:00:00Z",
        "provenance": "USER_ASSERTED",
    }
