"""SQLite persistence for workspace processing settings overrides."""

from notekeeper.application.ports import WorkspaceSettingsRepository
from notekeeper.domain import WorkspaceId, WorkspaceSettings

from .database import SQLiteDatabase


class SQLiteWorkspaceSettingsRepository(WorkspaceSettingsRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def get(self, workspace_id: WorkspaceId) -> WorkspaceSettings | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT workspace_settings.*, workspaces.name
                FROM workspace_settings
                JOIN workspaces ON workspaces.id = workspace_settings.workspace_id
                WHERE workspace_settings.workspace_id = ?
                """,
                (str(workspace_id),),
            ).fetchone()
        if row is None:
            return None
        return WorkspaceSettings(
            workspace_id=WorkspaceId(row["workspace_id"]),
            name=row["name"],
            whisperx_model_name=row["whisperx_model_name"],
            whisperx_language=row["whisperx_language"],
            deepseek_model_name=row["deepseek_model_name"],
            deepseek_temperature=row["deepseek_temperature"],
        )

    def save(self, settings: WorkspaceSettings) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_settings (
                    workspace_id, whisperx_model_name, whisperx_language,
                    deepseek_model_name, deepseek_temperature
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    whisperx_model_name = excluded.whisperx_model_name,
                    whisperx_language = excluded.whisperx_language,
                    deepseek_model_name = excluded.deepseek_model_name,
                    deepseek_temperature = excluded.deepseek_temperature
                """,
                (
                    str(settings.workspace_id),
                    settings.whisperx_model_name,
                    settings.whisperx_language,
                    settings.deepseek_model_name,
                    settings.deepseek_temperature,
                ),
            )

    def delete(self, workspace_id: WorkspaceId) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM workspace_settings WHERE workspace_id = ?",
                (str(workspace_id),),
            )


__all__ = ["SQLiteWorkspaceSettingsRepository"]
