"""SQLite workspace and membership repository."""

from notekeeper.application.ports import WorkspaceRepository
from notekeeper.domain import (
    UserId,
    Workspace,
    WorkspaceId,
    WorkspaceMembership,
    WorkspaceRole,
)

from .database import SQLiteDatabase
from .workspace_ids import personal_workspace_id


class SQLiteWorkspaceRepository(WorkspaceRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def get(self, workspace_id: WorkspaceId) -> Workspace | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT id, owner_user_id, name FROM workspaces WHERE id = ?",
                (str(workspace_id),),
            ).fetchone()
        return _workspace_from_row(row) if row is not None else None

    def list_for_user(self, user_id: UserId) -> tuple[Workspace, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT workspaces.id, workspaces.owner_user_id, workspaces.name
                FROM workspaces
                JOIN workspace_memberships
                  ON workspace_memberships.workspace_id = workspaces.id
                WHERE workspace_memberships.user_id = ?
                ORDER BY workspaces.rowid
                """,
                (str(user_id),),
            ).fetchall()
        return tuple(_workspace_from_row(row) for row in rows)

    def membership(
        self,
        workspace_id: WorkspaceId,
        user_id: UserId,
    ) -> WorkspaceMembership | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT workspace_id, user_id, role
                FROM workspace_memberships
                WHERE workspace_id = ? AND user_id = ?
                """,
                (str(workspace_id), str(user_id)),
            ).fetchone()
        if row is None:
            return None
        return WorkspaceMembership(
            workspace_id=WorkspaceId(row["workspace_id"]),
            user_id=UserId(row["user_id"]),
            role=WorkspaceRole(row["role"]),
        )

    def ensure_personal(self, user_id: UserId, name: str) -> WorkspaceMembership:
        workspace_id = personal_workspace_id(user_id)
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO workspaces (id, owner_user_id, name)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (str(workspace_id), str(user_id), name),
            )
            connection.execute(
                """
                INSERT INTO workspace_memberships (workspace_id, user_id, role)
                VALUES (?, ?, ?)
                ON CONFLICT(workspace_id, user_id) DO NOTHING
                """,
                (str(workspace_id), str(user_id), WorkspaceRole.OWNER.value),
            )
        return WorkspaceMembership(workspace_id, user_id, WorkspaceRole.OWNER)


def _workspace_from_row(row) -> Workspace:
    return Workspace(
        id=WorkspaceId(row["id"]),
        owner_user_id=UserId(row["owner_user_id"]),
        name=row["name"],
    )


__all__ = ["SQLiteWorkspaceRepository", "personal_workspace_id"]
