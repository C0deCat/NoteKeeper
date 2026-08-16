"""Mutable session controller owned by the local CLI/TUI adapters."""

from notekeeper.application import AccessContext, GetJobStatusCommand
from notekeeper.application.errors import AuthenticationRequiredError
from notekeeper.application.ports import DashboardEventStream, ProgressEventStream
from notekeeper.application.use_case_facade import ApplicationUseCases
from notekeeper.domain import ArtifactRef, AuthenticatedUser, ProcessingJob, ProcessingJobId
from notekeeper.interfaces import RuntimeDiagnostics

from .runtime import ApplicationSession, LocalApplicationHost


class LocalInterfaceRuntime:
    """Mutable UI-owned session controller; repositories remain immutable."""

    def __init__(self, host: LocalApplicationHost) -> None:
        self._host = host
        self._session = None if host.authenticator.enabled else host.root_session()

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
        return self._require_session().use_cases

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
    def cli_auth_session_path(self) -> str:
        return str(self._host.settings.cli_auth_session_path)

    def login(self, login: str, password: str) -> AuthenticatedUser:
        self._session = self._host.authenticate(login, password)
        return self._session.user

    def register(self, login: str, password: str) -> AuthenticatedUser:
        self._session = self._host.register(login, password)
        return self._session.user

    def logout(self) -> None:
        if self.enabled:
            self._session = None

    def require_user(self) -> AuthenticatedUser:
        return self._require_session().user

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
