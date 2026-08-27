"""Mutable session controller owned by the local CLI/TUI adapters."""

from notekeeper.application import AccessContext, GetJobStatusCommand
from notekeeper.application.errors import AuthenticationRequiredError, AuthorizationError
from notekeeper.application.ports import (
    ConsoleLogEventStream,
    DashboardEventStream,
    ProgressEventStream,
)
from notekeeper.application.use_case_facade import ApplicationUseCases
from notekeeper.domain import (
    ArtifactRef,
    AuthenticatedUser,
    ProcessingJob,
    ProcessingJobId,
    UserPreferences,
    Workspace,
    WorkspaceId,
)
from notekeeper.infrastructure.auth import LocalCliSessionStore
from notekeeper.interfaces import RuntimeDiagnostics

from .runtime import ApplicationSession, LocalApplicationHost


class LocalInterfaceRuntime:
    """Mutable UI-owned session controller; repositories remain immutable."""

    def __init__(self, host: LocalApplicationHost) -> None:
        self._host = host
        self._session = None if host.authenticator.enabled else host.root_session()
        self._requested_workspace_id: str | None = None

    @property
    def auth(self) -> "LocalInterfaceRuntime":
        return self

    @property
    def enabled(self) -> bool:
        return self._host.authenticator.enabled

    @property
    def current_user(self) -> AuthenticatedUser | None:
        return self._session.user if self._session is not None else None

    @property
    def use_cases(self) -> ApplicationUseCases:
        session = self._require_session()
        membership = self._host.services.workspace_repository.membership(
            session.access.workspace_id,
            session.user.id,
        )
        if membership is None:
            raise AuthorizationError("workspace access has been revoked")
        return session.use_cases

    @property
    def access(self) -> AccessContext:
        return self._require_session().access

    @property
    def progress_events(self) -> ProgressEventStream:
        return self._host.progress_events

    @property
    def dashboard_events(self) -> DashboardEventStream:
        return self._host.dashboard_events

    @property
    def console_logs(self) -> ConsoleLogEventStream:
        return self._host.console_logs

    @property
    def cli_auth_session_path(self) -> str:
        return str(self._host.settings.cli_auth_session_path)

    def login(self, login: str, password: str) -> AuthenticatedUser:
        self._session = self._host.authenticate(login, password)
        self._apply_requested_workspace()
        return self._session.user

    def register(self, login: str, password: str) -> AuthenticatedUser:
        self._session = self._host.register(login, password)
        self._apply_requested_workspace()
        return self._session.user

    def logout(self) -> None:
        if self.enabled:
            self._session = None

    def require_user(self) -> AuthenticatedUser:
        return self._require_session().user

    def list_workspaces(self) -> tuple[Workspace, ...]:
        user = self.require_user()
        return self._host.services.workspace_repository.list_for_user(user.id)

    def switch_workspace(self, workspace_id: str) -> Workspace:
        user = self.require_user()
        target = WorkspaceId(workspace_id)
        workspace = self._host.services.workspace_repository.get(target)
        if (
            workspace is None
            or self._host.services.workspace_repository.membership(target, user.id)
            is None
        ):
            raise AuthorizationError(f"workspace {target} is not accessible")
        self._session = self._host.session_for(user, target)
        self._host.services.user_preferences_repository.save(
            UserPreferences(user.id, target)
        )
        return workspace

    def request_workspace(self, workspace_id: str) -> None:
        self._requested_workspace_id = workspace_id
        if self._session is not None:
            self.switch_workspace(workspace_id)

    def _apply_requested_workspace(self) -> None:
        if self._requested_workspace_id is not None:
            self.switch_workspace(self._requested_workspace_id)

    def update_login(
        self,
        current_password: str,
        new_login: str,
    ) -> AuthenticatedUser:
        session = self._require_session()
        session_store = LocalCliSessionStore(self.cli_auth_session_path)
        cli_credentials = session_store.load()
        settings = session.use_cases.settings
        if settings is None:
            raise RuntimeError("settings service is unavailable")
        user = settings.update_login(current_password, new_login)
        if cli_credentials == (session.user.login, current_password):
            session_store.save(user.login, current_password)
        self._session = self._host.session_for(user, session.access.workspace_id)
        return user

    def update_password(
        self,
        current_password: str,
        new_password: str,
    ) -> AuthenticatedUser:
        session = self._require_session()
        session_store = LocalCliSessionStore(self.cli_auth_session_path)
        cli_credentials = session_store.load()
        settings = session.use_cases.settings
        if settings is None:
            raise RuntimeError("settings service is unavailable")
        user = settings.update_password(current_password, new_password)
        if cli_credentials == (session.user.login, current_password):
            session_store.save(user.login, new_password)
        return user

    def start_job_manager(self, *, recover_queued: bool = True) -> None:
        self._host.start_job_manager(recover_queued=recover_queued)

    def shutdown_job_manager(self) -> None:
        self._host.shutdown_job_manager()

    def wait_for_job(self, job_id: str) -> ProcessingJob:
        session = self._require_session()
        session.use_cases.jobs.get_status.execute(GetJobStatusCommand(job_id=job_id))
        return self._host.job_manager.wait_for_terminal(ProcessingJobId(job_id))

    def diagnostics(self, campaign_id: str | None = None) -> RuntimeDiagnostics:
        return self._host.diagnostics(self._require_session(), campaign_id)

    def format_artifact_location(self, artifact: ArtifactRef) -> str:
        self._require_session()
        return self._host.format_artifact_location(artifact)

    def _require_session(self) -> ApplicationSession:
        if self._session is None:
            raise AuthenticationRequiredError(
                "authentication required; run notekeeper auth login"
            )
        return self._session


__all__ = ["LocalInterfaceRuntime"]
