import sqlite3
from pathlib import Path

from notekeeper.domain import BUILTIN_ROOT_USER_ID
from notekeeper.infrastructure.sqlite import SQLiteDatabase


def test_existing_campaigns_are_migrated_to_root_owner(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE campaigns (id TEXT PRIMARY KEY, name TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO campaigns (id, name) VALUES ('legacy', 'Legacy')"
        )

    database = SQLiteDatabase(path)
    database.initialize()
    database.initialize()

    with database.connect() as connection:
        row = connection.execute(
            "SELECT owner_user_id FROM campaigns WHERE id = 'legacy'"
        ).fetchone()
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()

    assert row["owner_user_id"] == str(BUILTIN_ROOT_USER_ID)
    assert [version["version"] for version in versions] == [1]
