import sqlite3


def test_migration_1_database_upgrades_to_same_schema_as_fresh_database(tmp_path):
    from qualor.persistence import Database
    from qualor.persistence.migrations import MIGRATION_1

    upgraded_path = tmp_path / "upgraded.db"
    connection = sqlite3.connect(upgraded_path)
    connection.execute(
        "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    for statement in MIGRATION_1:
        connection.execute(statement)
    connection.execute("INSERT INTO schema_migrations VALUES (1, '2026-09-07T00:00:00Z')")
    connection.commit()
    connection.close()

    upgraded = Database(upgraded_path).connect()
    fresh = Database(tmp_path / "fresh.db").connect()
    try:

        def schema(db):
            return db.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' AND name != 'schema_migrations' ORDER BY type, name"
            ).fetchall()

        assert [tuple(row) for row in schema(upgraded)] == [tuple(row) for row in schema(fresh)]
        assert [row[0] for row in upgraded.execute("SELECT version FROM schema_migrations")] == [
            1,
            2,
        ]
        assert (
            upgraded.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' AND name='opportunity_refresh_failures'"
            ).fetchone()[0]
            == 1
        )
    finally:
        upgraded.close()
        fresh.close()
