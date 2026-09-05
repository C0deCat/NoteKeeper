"""Local API composition and Uvicorn runner."""

from __future__ import annotations

from pathlib import Path

import uvicorn

from notekeeper.domain import AuthenticatedUser, WorkspaceId
from notekeeper.infrastructure.auth import (
    BearerTokenPair,
    InMemoryApiSessionManager,
)
from notekeeper.interfaces.api import (
    ApiTokenGrant,
    ApiWorkspaceAccess,
    create_api_app,
)

from .runtime import (
    ApplicationSession,
    LocalApplicationHost,
    build_application_session,
    build_local_host,
)
from .settings import NoteKeeperSettings


class LocalApiRuntime:
    """Adapt the local composition root to the transport-facing API contract."""

    def __init__(
        self,
        host: LocalApplicationHost,
        sessions: InMemoryApiSessionManager,
    ) -> None:
        self._host = host
        self._sessions = sessions

    @property
    def upload_directory(self) -> Path:
        return self._host.settings.processing_work_root / "api-uploads"

    @property
    def upload_max_bytes(self) -> int:
        return self._host.settings.api_upload_max_bytes

    @property
    def audio_extensions(self) -> tuple[str, ...]:
        return self._host.settings.audio_extensions

    @property
    def sse_heartbeat_seconds(self) -> float:
        return self._host.settings.api_sse_heartbeat_seconds

    @property
    def progress_events(self):
        return self._host.progress_events

    def register(self, login: str, password: str) -> ApiTokenGrant:
        session = self._host.register(login, password)
        return self._grant(session.user, self._sessions.issue(session.user))

    def login(self, login: str, password: str) -> ApiTokenGrant:
        session = self._host.authenticate(login, password)
        return self._grant(session.user, self._sessions.issue(session.user))

    def refresh(self, refresh_token: str) -> ApiTokenGrant:
        user, pair = self._sessions.refresh(refresh_token)
        return self._grant(user, pair)

    def logout(self, refresh_token: str) -> None:
        self._sessions.revoke(refresh_token)

    def resolve_user(self, access_token: str) -> AuthenticatedUser:
        return self._sessions.resolve(access_token)

    def personal_session(self, user: AuthenticatedUser) -> ApplicationSession:
        return build_application_session(self._host, user)

    def workspace_session(
        self,
        user: AuthenticatedUser,
        workspace_id: str,
    ) -> ApplicationSession:
        return self._host.session_for(user, WorkspaceId(workspace_id))

    def list_workspaces(
        self,
        user: AuthenticatedUser,
    ) -> tuple[ApiWorkspaceAccess, ...]:
        session = self.personal_session(user)
        settings = session.use_cases.settings
        if settings is None:
            return ()
        return tuple(
            ApiWorkspaceAccess(
                workspace=workspace,
                role=self._host.session_for(user, workspace.id).access.role,
            )
            for workspace in settings.list_workspaces()
        )

    def start(self) -> None:
        self._host.start_job_manager(recover_queued=True)

    def shutdown(self) -> None:
        self._host.shutdown_job_manager()

    @staticmethod
    def _grant(
        user: AuthenticatedUser,
        pair: BearerTokenPair,
    ) -> ApiTokenGrant:
        return ApiTokenGrant(
            user=user,
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            access_expires_in=pair.access_expires_in,
            refresh_expires_in=pair.refresh_expires_in,
        )


def build_local_api_runtime(
    settings: NoteKeeperSettings | None = None,
) -> LocalApiRuntime:
    resolved = settings or NoteKeeperSettings()
    if not resolved.auth_enabled:
        raise ValueError(
            "notekeeper api requires NOTEKEEPER_AUTH_ENABLED=true"
        )
    host = build_local_host(resolved)
    sessions = InMemoryApiSessionManager(
        access_ttl_seconds=resolved.api_access_token_ttl_seconds,
        refresh_ttl_seconds=resolved.api_refresh_token_ttl_seconds,
    )
    return LocalApiRuntime(host, sessions)


def run_local_api(
    host: str | None = None,
    port: int | None = None,
) -> None:
    settings = NoteKeeperSettings()
    runtime = build_local_api_runtime(settings)
    uvicorn.run(
        create_api_app(runtime),
        host=host or settings.api_host,
        port=port or settings.api_port,
        workers=1,
    )


__all__ = ["LocalApiRuntime", "build_local_api_runtime", "run_local_api"]
