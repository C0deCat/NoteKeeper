"""Local host, immutable application sessions, and composition roots."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from notekeeper.application import (
    AccessContext,
    Authenticator,
    ListJobsForCampaignCommand,
    NotFoundError,
    WorkspaceScope,
)
from notekeeper.application.errors import ApplicationError
from notekeeper.application.use_case_facade import ApplicationUseCases
from notekeeper.application.use_cases.utils import CampaignMutationPolicy
from notekeeper.domain import (
    BUILTIN_ROOT_USER_ID,
    ArtifactRef,
    AuthenticatedUser,
    User,
    UserPreferences,
    WorkspaceId,
)
from notekeeper.infrastructure.auth import LocalAuthProvider
from notekeeper.infrastructure.runtime import (
    LocalDashboardCampaignRepositoryDecorator,
    LocalDashboardJobCleanerDecorator,
    LocalDashboardJobRepositoryDecorator,
    InMemoryDashboardEventHub,
    PersistedProgressEventHub,
    StreamingProgressTrackerFactory,
)
from notekeeper.infrastructure.sqlite import (
    SQLiteAudioTrackRepository,
    SQLiteCampaignRepository,
    SQLiteJobRepository,
    SQLiteParticipantRepository,
    SQLiteRecapRepository,
    SQLiteSpeakerMappingRepository,
    SQLiteSpeakerReviewSubmissionRepository,
    SQLiteTranscriptRepository,
    SQLiteVoiceSampleRepository,
)
from notekeeper.interfaces import RuntimeDiagnostics

from .factory import LocalServices, build_local_services
from .job_pipeline import build_processing_pipeline
from notekeeper.infrastructure.runtime.jobs import LocalJobManager
from .repositories import SystemRepositories, WorkspaceRepositories
from .settings import NoteKeeperSettings
from .use_cases import wire_application_use_cases
from .worker import execute_worker_process

if TYPE_CHECKING:
    from .local_interface_runtime import LocalInterfaceRuntime


@dataclass(frozen=True, slots=True)
class ApplicationSession:
    user: AuthenticatedUser
    access: AccessContext
    use_cases: ApplicationUseCases


@dataclass(frozen=True, slots=True)
class LocalApplicationHost:
    settings: NoteKeeperSettings
    authenticator: Authenticator
    services: LocalServices
    system_repositories: SystemRepositories
    progress_events: PersistedProgressEventHub
    dashboard_events: InMemoryDashboardEventHub
    job_manager: LocalJobManager

    def authenticate(self, login: str, password: str) -> ApplicationSession:
        user = self.authenticator.authenticate(login, password)
        return _build_preferred_application_session(
            self, user, publish_dashboard_events=True
        )

    def register(self, login: str, password: str) -> ApplicationSession:
        user = self.authenticator.register(login, password)
        session = _build_application_session(
            self, user, publish_dashboard_events=True
        )
        self.services.user_preferences_repository.save(
            UserPreferences(user.id, session.access.workspace_id)
        )
        return session

    def root_session(self) -> ApplicationSession:
        return _build_application_session(
            self,
            User(BUILTIN_ROOT_USER_ID, "root"),
            publish_dashboard_events=True,
        )

    def session_for(
        self,
        user: AuthenticatedUser,
        workspace_id: WorkspaceId,
    ) -> ApplicationSession:
        return _build_application_session(
            self,
            user,
            workspace_id,
            publish_dashboard_events=True,
        )

    def interactive_runtime(self) -> LocalInterfaceRuntime:
        from .local_interface_runtime import LocalInterfaceRuntime

        return LocalInterfaceRuntime(self)

    def start_job_manager(self, *, recover_queued: bool = True) -> None:
        self.job_manager.start(recover_queued=recover_queued)

    def shutdown_job_manager(self) -> None:
        self.job_manager.shutdown()

    def diagnostics(
        self,
        session: ApplicationSession,
        campaign_id: str | None = None,
    ) -> RuntimeDiagnostics:
        mutable_settings = session.use_cases.settings
        effective = (
            mutable_settings.get_workspace()
            if mutable_settings is not None
            else None
        )
        return RuntimeDiagnostics(
            storage_root=_path_text(self.settings.storage_root),
            sqlite_path=_path_text(self.settings.sqlite_path),
            processing_work_root=_path_text(self.settings.processing_work_root),
            whisperx_model_name=(
                effective.whisperx_model_name
                if effective is not None
                else self.settings.whisperx_model_name
            ),
            whisperx_device=self.settings.whisperx_device,
            whisperx_compute_type=self.settings.whisperx_compute_type,
            whisperx_vad_method=self.settings.whisperx_vad_method,
            deepseek_configured=bool(self.settings.deepseek_api_key),
            huggingface_configured=bool(self.settings.whisperx_hf_token),
            recent_messages=_recent_messages(session.use_cases, campaign_id),
            whisperx_language=(
                effective.whisperx_language
                if effective is not None
                else self.settings.whisperx_language
            ),
            deepseek_model_name=(
                effective.deepseek_model_name
                if effective is not None
                else self.settings.deepseek_model_name
            ),
            deepseek_temperature=(
                effective.deepseek_temperature
                if effective is not None
                else self.settings.deepseek_temperature
            ),
        )

    def format_artifact_location(self, artifact: ArtifactRef) -> str:
        if artifact.kind != "file":
            return artifact.uri
        return _path_text(self.settings.storage_root / Path(artifact.uri))


def build_local_host(
    settings: NoteKeeperSettings | None = None,
) -> LocalApplicationHost:
    services = build_local_services(settings)
    if services.settings.auth_provider != "local":
        raise ValueError(
            f"unsupported auth provider: {services.settings.auth_provider}"
        )
    authenticator = Authenticator(
        LocalAuthProvider(services.settings.local_auth_users_path),
        enabled=services.settings.auth_enabled,
    )
    services.transient_audio_cleaner.clean_stale()
    progress_events = PersistedProgressEventHub(services.progress_event_snapshot_store)
    dashboard_events = InMemoryDashboardEventHub()
    system_repositories = _with_dashboard_events(
        services.repositories,
        dashboard_events,
    )
    pipeline = build_processing_pipeline(services, system_repositories)
    job_manager = _build_local_job_manager(
        services,
        system_repositories,
        pipeline,
        progress_events,
        dashboard_events,
    )
    return LocalApplicationHost(
        settings=services.settings,
        authenticator=authenticator,
        services=services,
        system_repositories=system_repositories,
        progress_events=progress_events,
        dashboard_events=dashboard_events,
        job_manager=job_manager,
    )


def build_application_session(
    host: LocalApplicationHost,
    user: AuthenticatedUser,
    workspace_id: WorkspaceId | None = None,
) -> ApplicationSession:
    return _build_application_session(
        host,
        user,
        workspace_id,
        publish_dashboard_events=False,
    )


def _build_application_session(
    host: LocalApplicationHost,
    user: AuthenticatedUser,
    workspace_id: WorkspaceId | None = None,
    *,
    publish_dashboard_events: bool,
) -> ApplicationSession:
    workspace_repository = host.services.workspace_repository
    if workspace_id is None:
        membership = workspace_repository.ensure_personal(
            user.id,
            f"{user.login}'s workspace",
        )
    else:
        membership = workspace_repository.membership(workspace_id, user.id)
        if membership is None:
            raise NotFoundError(f"workspace {workspace_id} was not found")
    access = AccessContext(user.id, membership.workspace_id, membership.role)
    repositories = _build_workspace_repositories(
        host,
        access,
        publish_dashboard_events=publish_dashboard_events,
    )
    mutation_policy = CampaignMutationPolicy(
        repositories.job_repository,
        _campaign_mutation_guard(host.services),
    )
    session_services = host.services
    if publish_dashboard_events:
        session_services = replace(
            host.services,
            job_cleaner=LocalDashboardJobCleanerDecorator(
                host.services.job_cleaner,
                host.dashboard_events,
            ),
        )
    use_cases = wire_application_use_cases(
        session_services,
        repositories,
        progress_tracker_factory=StreamingProgressTrackerFactory(host.progress_events),
        job_manager=host.job_manager,
        mutation_policy=mutation_policy,
        access=access,
        authenticator=host.authenticator,
    )
    return ApplicationSession(user, access, use_cases)


def _build_preferred_application_session(
    host: LocalApplicationHost,
    user: AuthenticatedUser,
    *,
    publish_dashboard_events: bool,
) -> ApplicationSession:
    personal = host.services.workspace_repository.ensure_personal(
        user.id,
        f"{user.login}'s workspace",
    )
    preferences = host.services.user_preferences_repository.get(user.id)
    workspace_id = (
        preferences.default_workspace_id if preferences is not None else None
    )
    if (
        workspace_id is None
        or host.services.workspace_repository.membership(workspace_id, user.id) is None
    ):
        workspace_id = personal.workspace_id
        host.services.user_preferences_repository.save(
            UserPreferences(user.id, workspace_id)
        )
    return _build_application_session(
        host,
        user,
        workspace_id,
        publish_dashboard_events=publish_dashboard_events,
    )


def _build_workspace_repositories(
    host: LocalApplicationHost,
    access: AccessContext,
    *,
    publish_dashboard_events: bool,
) -> WorkspaceRepositories:
    services = host.services
    scope = WorkspaceScope(access.workspace_id)
    campaign_repository = SQLiteCampaignRepository(services.database, scope)
    job_repository = SQLiteJobRepository(services.database, scope)
    if publish_dashboard_events:
        campaign_repository = LocalDashboardCampaignRepositoryDecorator(
            campaign_repository,
            host.dashboard_events,
        )
        job_repository = LocalDashboardJobRepositoryDecorator(
            job_repository,
            host.dashboard_events,
        )
    return WorkspaceRepositories(
        campaign_repository=campaign_repository,
        participant_repository=SQLiteParticipantRepository(services.database, scope),
        voice_sample_repository=SQLiteVoiceSampleRepository(services.database, scope),
        audio_track_repository=SQLiteAudioTrackRepository(services.database, scope),
        transcript_repository=SQLiteTranscriptRepository(
            services.database, services.artifact_storage, scope
        ),
        recap_repository=SQLiteRecapRepository(
            services.database, services.artifact_storage, scope
        ),
        job_repository=job_repository,
        speaker_mapping_repository=SQLiteSpeakerMappingRepository(
            services.database, scope
        ),
        speaker_review_submission_repository=(
            SQLiteSpeakerReviewSubmissionRepository(services.database, scope)
        ),
    )


def _with_dashboard_events(
    repositories: SystemRepositories,
    events: InMemoryDashboardEventHub,
) -> SystemRepositories:
    return replace(
        repositories,
        campaign_repository=LocalDashboardCampaignRepositoryDecorator(
            repositories.campaign_repository,
            events,
        ),
        job_repository=LocalDashboardJobRepositoryDecorator(
            repositories.job_repository,
            events,
        ),
    )


def _campaign_mutation_guard(services: LocalServices):
    from notekeeper.infrastructure.runtime import LocalCampaignMutationGuard

    return LocalCampaignMutationGuard(_job_lock_root(services.settings))


def _build_local_job_manager(
    services: LocalServices,
    repositories: SystemRepositories,
    processing_pipeline,
    progress_events: PersistedProgressEventHub,
    dashboard_events: InMemoryDashboardEventHub,
) -> LocalJobManager:
    return LocalJobManager(
        services.settings,
        processing_pipeline,
        repositories.campaign_repository,
        repositories.job_repository,
        services.clock,
        worker_target=execute_worker_process,
        lock_root=_job_lock_root(services.settings),
        progress_events=progress_events,
        dashboard_events=dashboard_events,
        transient_audio_cleaner=services.transient_audio_cleaner,
        review_submission_repository=(
            repositories.speaker_review_submission_repository
        ),
    )


def _job_lock_root(settings: NoteKeeperSettings) -> Path:
    sqlite_path = settings.sqlite_path.resolve(strict=False)
    return sqlite_path.parent / f".{sqlite_path.name}.locks"


def _recent_messages(
    use_cases: ApplicationUseCases,
    campaign_id: str | None,
) -> tuple[str, ...]:
    if campaign_id is None:
        return ()
    try:
        jobs = use_cases.jobs.list_for_campaign.execute(
            ListJobsForCampaignCommand(campaign_id=campaign_id)
        ).jobs
    except ApplicationError as exc:
        return (str(exc),)
    messages: list[str] = []
    for job in reversed(jobs):
        if job.error_message:
            messages.append(f"{job.id}: {job.error_message}")
        for warning in job.warnings:
            messages.append(f"{job.id}: {warning.message}")
        if len(messages) >= 8:
            break
    return tuple(messages[:8])


def _path_text(path: Path) -> str:
    return str(path.resolve(strict=False))


__all__ = [
    "ApplicationSession",
    "LocalApplicationHost",
    "build_application_session",
    "build_local_host",
]
