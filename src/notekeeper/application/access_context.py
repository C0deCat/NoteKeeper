"""Immutable actor and repository access scopes."""

from dataclasses import dataclass

from notekeeper.domain import UserId, WorkspaceId, WorkspaceRole


@dataclass(frozen=True, slots=True)
class AccessContext:
    actor_user_id: UserId
    workspace_id: WorkspaceId
    role: WorkspaceRole


@dataclass(frozen=True, slots=True)
class SystemScope:
    """Explicit marker for trusted cross-workspace infrastructure."""


@dataclass(frozen=True, slots=True)
class WorkspaceScope:
    workspace_id: WorkspaceId


RepositoryScope = SystemScope | WorkspaceScope
SYSTEM_SCOPE = SystemScope()

__all__ = [
    "AccessContext",
    "RepositoryScope",
    "SYSTEM_SCOPE",
    "SystemScope",
    "WorkspaceScope",
]
