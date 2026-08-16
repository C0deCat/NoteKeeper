"""Workspace tenancy entities."""

from dataclasses import dataclass

from ..enums import WorkspaceRole
from ..ids import UserId, WorkspaceId
from ..validation import non_empty_str


@dataclass(frozen=True, slots=True)
class Workspace:
    id: WorkspaceId
    owner_user_id: UserId
    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", non_empty_str(self.name, "name"))


@dataclass(frozen=True, slots=True)
class WorkspaceMembership:
    workspace_id: WorkspaceId
    user_id: UserId
    role: WorkspaceRole


__all__ = ["Workspace", "WorkspaceMembership"]
