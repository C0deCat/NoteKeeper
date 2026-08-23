"""Contracts shared by UI adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from notekeeper.application.ports import DashboardEventStream, ProgressEventStream
from notekeeper.application.use_case_facade import ApplicationUseCases
from notekeeper.domain import ArtifactRef, AuthenticatedUser, ProcessingJob, Workspace


class AuthRuntime(Protocol):
    @property
    def enabled(self) -> bool: ...

    @property
    def current_user(self) -> AuthenticatedUser | None: ...

    def login(self, login: str, password: str) -> AuthenticatedUser: ...

    def register(self, login: str, password: str) -> AuthenticatedUser: ...

    def logout(self) -> None: ...

    def require_user(self) -> AuthenticatedUser: ...

    def update_login(
        self, current_password: str, new_login: str
    ) -> AuthenticatedUser: ...

    def update_password(
        self, current_password: str, new_password: str
    ) -> AuthenticatedUser: ...


@dataclass(frozen=True, slots=True)
class RuntimeDiagnostics:
    storage_root: str
    sqlite_path: str
    processing_work_root: str
    whisperx_model_name: str
    whisperx_device: str
    whisperx_compute_type: str
    whisperx_vad_method: str
    deepseek_configured: bool
    huggingface_configured: bool
    recent_messages: tuple[str, ...] = ()
    whisperx_language: str | None = None
    deepseek_model_name: str = ""
    deepseek_temperature: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "recent_messages", tuple(self.recent_messages))


class InterfaceRuntime(Protocol):
    @property
    def auth(self) -> AuthRuntime: ...
    @property
    def use_cases(self) -> ApplicationUseCases: ...

    @property
    def progress_events(self) -> ProgressEventStream: ...

    @property
    def dashboard_events(self) -> DashboardEventStream: ...

    def start_job_manager(self, *, recover_queued: bool = True) -> None: ...

    def shutdown_job_manager(self) -> None: ...

    def wait_for_job(self, job_id: str) -> ProcessingJob: ...

    def diagnostics(self, campaign_id: str | None = None) -> RuntimeDiagnostics: ...

    def format_artifact_location(self, artifact: ArtifactRef) -> str: ...

    def list_workspaces(self) -> tuple[Workspace, ...]: ...

    def switch_workspace(self, workspace_id: str) -> Workspace: ...

    def request_workspace(self, workspace_id: str) -> None: ...

    @property
    def cli_auth_session_path(self) -> str: ...
