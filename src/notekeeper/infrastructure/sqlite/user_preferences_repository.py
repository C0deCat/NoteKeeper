"""SQLite persistence for user interface preferences."""

from notekeeper.application.ports import UserPreferencesRepository
from notekeeper.domain import UserId, UserPreferences, WorkspaceId

from .database import SQLiteDatabase


class SQLiteUserPreferencesRepository(UserPreferencesRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def get(self, user_id: UserId) -> UserPreferences | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT user_id, default_workspace_id FROM user_preferences WHERE user_id = ?",
                (str(user_id),),
            ).fetchone()
        if row is None:
            return None
        return UserPreferences(
            user_id=UserId(row["user_id"]),
            default_workspace_id=(
                WorkspaceId(row["default_workspace_id"])
                if row["default_workspace_id"] is not None
                else None
            ),
        )

    def save(self, preferences: UserPreferences) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_preferences (user_id, default_workspace_id)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    default_workspace_id = excluded.default_workspace_id
                """,
                (
                    str(preferences.user_id),
                    str(preferences.default_workspace_id)
                    if preferences.default_workspace_id is not None
                    else None,
                ),
            )


__all__ = ["SQLiteUserPreferencesRepository"]
