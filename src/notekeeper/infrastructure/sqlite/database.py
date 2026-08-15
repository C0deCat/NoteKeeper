"""SQLite database setup."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .schema import SCHEMA

from notekeeper.domain import BUILTIN_ROOT_USER_ID

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
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (1)"
            )


__all__ = ["SQLiteDatabase"]
