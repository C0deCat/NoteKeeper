"""SQLite database setup."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .schema import SCHEMA

from notekeeper.domain import BUILTIN_ROOT_USER_ID
from notekeeper.domain import UserId

from .workspace_ids import personal_workspace_id

_MIGRATION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


class SQLiteDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        if self.path != Path(":memory:"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(_MIGRATION_TABLE)
            self._apply_migrations(connection)
            connection.executescript(SCHEMA)

    @staticmethod
    def _apply_migrations(connection: sqlite3.Connection) -> None:
        applied = {
            int(row["version"])
            for row in connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }
        if 1 not in applied:
            table_exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'campaigns'"
            ).fetchone()
            if table_exists is not None:
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(campaigns)")
                }
                if "owner_user_id" not in columns:
                    connection.execute(
                        "ALTER TABLE campaigns ADD COLUMN owner_user_id "
                        f"TEXT NOT NULL DEFAULT '{BUILTIN_ROOT_USER_ID}'"
                    )
            connection.execute("INSERT INTO schema_migrations (version) VALUES (1)")
        if 2 not in applied:
            SQLiteDatabase._migrate_workspaces(connection)
            connection.execute("INSERT INTO schema_migrations (version) VALUES (2)")

    @staticmethod
    def _migrate_workspaces(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                name TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_memberships (
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                PRIMARY KEY (workspace_id, user_id)
            )
            """
        )
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'campaigns'"
        ).fetchone()
        if table_exists is None:
            return
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(campaigns)")
        }
        if "workspace_id" in columns:
            return
        owners = connection.execute(
            "SELECT DISTINCT owner_user_id FROM campaigns"
        ).fetchall()
        for row in owners:
            user_id = UserId(row["owner_user_id"])
            workspace_id = personal_workspace_id(user_id)
            connection.execute(
                "INSERT OR IGNORE INTO workspaces (id, owner_user_id, name) VALUES (?, ?, ?)",
                (str(workspace_id), str(user_id), "Personal workspace"),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO workspace_memberships
                    (workspace_id, user_id, role)
                VALUES (?, ?, 'owner')
                """,
                (str(workspace_id), str(user_id)),
            )
        connection.execute(
            """
            CREATE TABLE campaigns_v2 (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                workspace_id TEXT NOT NULL
            )
            """
        )
        for row in connection.execute(
            "SELECT id, name, owner_user_id FROM campaigns"
        ).fetchall():
            workspace_id = personal_workspace_id(UserId(row["owner_user_id"]))
            connection.execute(
                "INSERT INTO campaigns_v2 (id, name, workspace_id) VALUES (?, ?, ?)",
                (row["id"], row["name"], str(workspace_id)),
            )
        connection.execute("DROP TABLE campaigns")
        connection.execute("ALTER TABLE campaigns_v2 RENAME TO campaigns")


__all__ = ["SQLiteDatabase"]
