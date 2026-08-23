"""Stable identifiers used by local personal workspaces."""

from uuid import UUID, uuid5

from notekeeper.domain import UserId, WorkspaceId

_PERSONAL_WORKSPACE_NAMESPACE = UUID("72dc177f-873d-4b25-9790-019121a71e08")


def personal_workspace_id(user_id: UserId) -> WorkspaceId:
    return WorkspaceId(str(uuid5(_PERSONAL_WORKSPACE_NAMESPACE, str(user_id))))


__all__ = ["personal_workspace_id"]
