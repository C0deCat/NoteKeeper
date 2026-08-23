import sqlite3
from pathlib import Path

from notekeeper.domain import BUILTIN_ROOT_USER_ID, UserId
from notekeeper.infrastructure.sqlite import personal_workspace_id
from notekeeper.infrastructure.sqlite import SQLiteDatabase


def test_existing_campaigns_are_migrated_to_root_workspace(tmp_path: Path) -> None:
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
            "SELECT workspace_id FROM campaigns WHERE id = 'legacy'"
        ).fetchone()
        membership = connection.execute(
            """
            SELECT role FROM workspace_memberships
            WHERE workspace_id = ? AND user_id = ?
            """,
            (
                str(personal_workspace_id(BUILTIN_ROOT_USER_ID)),
                str(BUILTIN_ROOT_USER_ID),
            ),
        ).fetchone()
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()

    assert row["workspace_id"] == str(personal_workspace_id(BUILTIN_ROOT_USER_ID))
    assert membership["role"] == "owner"
    assert [version["version"] for version in versions] == [1, 2, 3]


def test_migration_groups_legacy_campaigns_by_owner_without_duplicates(
    tmp_path: Path,
) -> None:
    path = tmp_path / "owned-legacy.sqlite3"
    alice = UserId("alice-id")
    bob = UserId("bob-id")
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE campaigns (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_user_id TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO campaigns (id, name, owner_user_id) VALUES (?, ?, ?)",
            (
                ("alice-1", "Alice one", str(alice)),
                ("alice-2", "Alice two", str(alice)),
                ("bob-1", "Bob one", str(bob)),
            ),
        )

    database = SQLiteDatabase(path)
    database.initialize()
    database.initialize()

    with database.connect() as connection:
        campaigns = connection.execute(
            "SELECT id, workspace_id FROM campaigns ORDER BY id"
        ).fetchall()
        workspaces = connection.execute("SELECT id FROM workspaces").fetchall()
        memberships = connection.execute(
            "SELECT workspace_id, user_id, role FROM workspace_memberships"
        ).fetchall()

    assert [(row["id"], row["workspace_id"]) for row in campaigns] == [
        ("alice-1", str(personal_workspace_id(alice))),
        ("alice-2", str(personal_workspace_id(alice))),
        ("bob-1", str(personal_workspace_id(bob))),
    ]
    assert {row["id"] for row in workspaces} == {
        str(personal_workspace_id(alice)),
        str(personal_workspace_id(bob)),
    }
    assert {
        (row["workspace_id"], row["user_id"], row["role"])
        for row in memberships
    } == {
        (str(personal_workspace_id(alice)), str(alice), "owner"),
        (str(personal_workspace_id(bob)), str(bob), "owner"),
    }
