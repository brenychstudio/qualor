"""Ordered, immutable SQLite migrations."""

import sqlite3
from datetime import UTC, datetime


class UnsupportedSchemaError(RuntimeError):
    """The database migration history is not a supported contiguous prefix."""


MIGRATION_1 = (
    """CREATE TABLE founder_profiles (
        id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
        record_json TEXT NOT NULL CHECK(json_valid(record_json)), created_at TEXT NOT NULL,
        PRIMARY KEY(id, version)
    )""",
    """CREATE TABLE project_profiles (
        id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
        record_json TEXT NOT NULL CHECK(json_valid(record_json)), created_at TEXT NOT NULL,
        PRIMARY KEY(id, version)
    )""",
    """CREATE TABLE opportunity_versions (
        id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
        record_json TEXT NOT NULL CHECK(json_valid(record_json)), content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL, PRIMARY KEY(id, version)
    )""",
    """CREATE TABLE evidence (
        id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
        opportunity_id TEXT NOT NULL, opportunity_version INTEGER NOT NULL,
        record_json TEXT NOT NULL CHECK(json_valid(record_json)), created_at TEXT NOT NULL,
        PRIMARY KEY(id, version),
        FOREIGN KEY(opportunity_id, opportunity_version)
            REFERENCES opportunity_versions(id, version)
    )""",
    """CREATE TABLE decisions (
        id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
        opportunity_id TEXT NOT NULL, opportunity_version INTEGER NOT NULL,
        founder_profile_id TEXT NOT NULL, founder_profile_version INTEGER NOT NULL,
        project_id TEXT NOT NULL, project_version INTEGER NOT NULL,
        record_json TEXT NOT NULL CHECK(json_valid(record_json)), created_at TEXT NOT NULL,
        PRIMARY KEY(id, version),
        FOREIGN KEY(opportunity_id, opportunity_version)
            REFERENCES opportunity_versions(id, version),
        FOREIGN KEY(founder_profile_id, founder_profile_version)
            REFERENCES founder_profiles(id, version),
        FOREIGN KEY(project_id, project_version) REFERENCES project_profiles(id, version)
    )""",
    """CREATE TABLE runs (
        id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
        record_json TEXT NOT NULL CHECK(json_valid(record_json)),
        mode TEXT NOT NULL CHECK(mode IN ('FIXTURE','REPLAY','LIVE')),
        state TEXT NOT NULL CHECK(state IN
            ('CREATED','RUNNING','COMPLETED','PARTIAL','FAILED','CANCELLED','BUDGET_STOPPED')),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY(id, version), UNIQUE(id)
    )""",
    """CREATE TABLE run_events (
        run_id TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence > 0),
        event_type TEXT NOT NULL CHECK(length(event_type) BETWEEN 1 AND 80),
        payload_json TEXT NOT NULL CHECK(
            json_valid(payload_json) AND length(CAST(payload_json AS BLOB)) <= 4096
        ),
        mode TEXT NOT NULL CHECK(mode IN ('FIXTURE','REPLAY','LIVE')),
        occurred_at TEXT NOT NULL, PRIMARY KEY(run_id, sequence),
        FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE RESTRICT
    )""",
    """CREATE TRIGGER run_events_no_update BEFORE UPDATE ON run_events
        BEGIN SELECT RAISE(ABORT, 'run events are append-only'); END""",
    """CREATE TRIGGER run_events_no_delete BEFORE DELETE ON run_events
        BEGIN SELECT RAISE(ABORT, 'run events are append-only'); END""",
    """CREATE TABLE approvals (
        id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
        opportunity_id TEXT NOT NULL, opportunity_version INTEGER NOT NULL,
        founder_profile_id TEXT NOT NULL, founder_profile_version INTEGER NOT NULL,
        project_id TEXT NOT NULL, project_version INTEGER NOT NULL,
        decision_id TEXT NOT NULL, decision_version INTEGER NOT NULL,
        record_json TEXT NOT NULL CHECK(json_valid(record_json)),
        state TEXT NOT NULL CHECK(state IN
            ('NOT_REVIEWED','PENDING_APPROVAL','APPROVED_FOR_PREPARATION',
             'REVOKED_APPROVAL','DRAFT_READY')),
        idempotency_key TEXT, created_at TEXT NOT NULL, PRIMARY KEY(id, version),
        FOREIGN KEY(opportunity_id, opportunity_version)
            REFERENCES opportunity_versions(id, version),
        FOREIGN KEY(founder_profile_id, founder_profile_version)
            REFERENCES founder_profiles(id, version),
        FOREIGN KEY(project_id, project_version) REFERENCES project_profiles(id, version),
        FOREIGN KEY(decision_id, decision_version) REFERENCES decisions(id, version),
        UNIQUE(idempotency_key)
    )""",
    """CREATE TABLE draft_jobs (
        id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0), approval_id TEXT NOT NULL,
        approval_version INTEGER NOT NULL, record_json TEXT NOT NULL CHECK(json_valid(record_json)),
        state TEXT NOT NULL CHECK(state IN
            ('CREATED','RUNNING','COMPLETED','FAILED','CANCELLED','BUDGET_STOPPED')),
        idempotency_key TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(id, version),
        FOREIGN KEY(approval_id, approval_version) REFERENCES approvals(id, version),
        UNIQUE(approval_id, idempotency_key)
    )""",
    """CREATE TABLE draft_packs (
        id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
        draft_job_id TEXT NOT NULL, draft_job_version INTEGER NOT NULL,
        approval_id TEXT NOT NULL, approval_version INTEGER NOT NULL,
        record_json TEXT NOT NULL CHECK(json_valid(record_json)), created_at TEXT NOT NULL,
        PRIMARY KEY(id, version), UNIQUE(draft_job_id, draft_job_version),
        FOREIGN KEY(draft_job_id, draft_job_version) REFERENCES draft_jobs(id, version),
        FOREIGN KEY(approval_id, approval_version) REFERENCES approvals(id, version)
    )""",
)

MIGRATIONS: tuple[tuple[str, ...], ...] = (MIGRATION_1,)


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    versions = [row[0] for row in connection.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    )]
    expected = list(range(1, len(versions) + 1))
    if versions != expected or (versions and versions[-1] > len(MIGRATIONS)):
        raise UnsupportedSchemaError(f"Unsupported schema migration history: {versions}")

    for version, statements in enumerate(MIGRATIONS, start=1):
        if version in versions:
            continue
        try:
            connection.execute("BEGIN IMMEDIATE")
            for statement in statements:
                connection.execute(statement)
            applied_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, applied_at),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
