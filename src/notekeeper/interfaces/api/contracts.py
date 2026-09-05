"""Runtime contracts consumed by the HTTP interface adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from notekeeper.application import AccessContext, ApplicationUseCases
from notekeeper.application.ports import ProgressEventStream
from notekeeper.domain import AuthenticatedUser, Workspace, WorkspaceRole


@dataclass(frozen=True, slots=True)
class ApiTokenGrant:
    user: AuthenticatedUser
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int


@dataclass(frozen=True, slots=True)
class ApiWorkspaceAccess:
    workspace: Workspace
    role: WorkspaceRole


class ApiSession(Protocol):
    user: AuthenticatedUser
    access: AccessContext
    use_cases: ApplicationUseCases


class ApiRuntime(Protocol):
    @property
    def upload_directory(self) -> Path: ...

    @property
    def upload_max_bytes(self) -> int: ...

    @property
    def audio_extensions(self) -> tuple[str, ...]: ...

    @property
    def sse_heartbeat_seconds(self) -> float: ...

    @property
    def progress_events(self) -> ProgressEventStream: ...

    def register(self, login: str, password: str) -> ApiTokenGrant: ...

    def login(self, login: str, password: str) -> ApiTokenGrant: ...

    def refresh(self, refresh_token: str) -> ApiTokenGrant: ...

    def logout(self, refresh_token: str) -> None: ...

    def resolve_user(self, access_token: str) -> AuthenticatedUser: ...

    def personal_session(self, user: AuthenticatedUser) -> ApiSession: ...

    def workspace_session(
        self,
        user: AuthenticatedUser,
        workspace_id: str,
    ) -> ApiSession: ...

    def list_workspaces(
        self,
        user: AuthenticatedUser,
    ) -> tuple[ApiWorkspaceAccess, ...]: ...

    def start(self) -> None: ...

    def shutdown(self) -> None: ...


__all__ = [
    "ApiRuntime",
    "ApiSession",
    "ApiTokenGrant",
    "ApiWorkspaceAccess",
]
