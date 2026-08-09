"""Runtime assembly for user interfaces."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from notekeeper.application import (
    ExecuteQueuedProcessingJob,
    ListJobsForCampaignCommand,
)
from notekeeper.application.errors import ApplicationError
from notekeeper.application.ports import (
    DashboardEventStream,
    JobManager,
    ProgressEventHub,
    ProgressEventStream,
)
from notekeeper.application.use_cases.utils import CampaignMutationPolicy
from notekeeper.domain import ArtifactRef, ProcessingJob, ProcessingJobId
from notekeeper.infrastructure.runtime import (
    EventPublishingCampaignRepository,
    EventPublishingJobCleaner,
    EventPublishingJobRepository,
    InMemoryDashboardEventHub,
    InMemoryProgressEventHub,
    LocalCampaignMutationGuard,
    MutationGuardingCampaignRepository,
    PersistedProgressEventHub,
    StreamingProgressTrackerFactory,
)
from notekeeper.interfaces import RuntimeDiagnostics, Stage1UseCases

from .factory import InfrastructureBundle, build_infrastructure
from .job_pipeline import build_processing_pipeline
from .process_job_executor import LocalJobManager
from .settings import NoteKeeperSettings
from .stage1_use_cases import wire_stage1_use_cases


@dataclass(frozen=True, slots=True)
class NoteKeeperRuntime:
    settings: NoteKeeperSettings
    use_cases: Stage1UseCases
    infrastructure: InfrastructureBundle
    progress_events: ProgressEventStream
    dashboard_events: DashboardEventStream
    job_manager: LocalJobManager

    def start_job_manager(self, *, recover_queued: bool = True) -> None:
        self.job_manager.start(recover_queued=recover_queued)

    def shutdown_job_manager(self) -> None:
        self.job_manager.shutdown()

    def wait_for_job(self, job_id: str) -> ProcessingJob:
        return self.job_manager.wait_for_terminal(ProcessingJobId(job_id))

    def diagnostics(self, campaign_id: str | None = None) -> RuntimeDiagnostics:
        return RuntimeDiagnostics(
            storage_root=_path_text(self.settings.storage_root),
            sqlite_path=_path_text(self.settings.sqlite_path),
            processing_work_root=_path_text(self.settings.processing_work_root),
            whisperx_model_name=self.settings.whisperx_model_name,
            whisperx_device=self.settings.whisperx_device,
            whisperx_compute_type=self.settings.whisperx_compute_type,
            whisperx_vad_method=self.settings.whisperx_vad_method,
            deepseek_configured=bool(self.settings.deepseek_api_key),
            huggingface_configured=bool(self.settings.whisperx_hf_token),
            recent_messages=_recent_messages(self.use_cases, campaign_id),
        )

    def format_artifact_location(self, artifact: ArtifactRef) -> str:
        if artifact.kind != "file":
            return artifact.uri
        return _path_text(self.settings.storage_root / Path(artifact.uri))


def build_runtime(settings: NoteKeeperSettings | None = None) -> NoteKeeperRuntime:
    infrastructure = build_infrastructure(settings)
    infrastructure.transient_audio_cleaner.clean_stale()
    progress_events = PersistedProgressEventHub(
        infrastructure.progress_event_snapshot_store
    )
    dashboard_events = InMemoryDashboardEventHub()
    infrastructure = replace(
        infrastructure,
        campaign_repository=EventPublishingCampaignRepository(
            infrastructure.campaign_repository,
            dashboard_events,
        ),
        job_repository=EventPublishingJobRepository(
            infrastructure.job_repository,
            dashboard_events,
        ),
        job_cleaner=EventPublishingJobCleaner(
            infrastructure.job_cleaner,
            dashboard_events,
        ),
    )
    processing_pipeline = build_processing_pipeline(infrastructure)
    mutation_policy = _build_campaign_mutation_policy(infrastructure)
    job_manager = _build_local_job_manager(
        infrastructure,
        processing_pipeline,
        progress_events,
        dashboard_events,
    )
    return NoteKeeperRuntime(
        settings=infrastructure.settings,
        use_cases=build_stage1_use_cases(
            infrastructure,
            progress_events=progress_events,
            dashboard_events=dashboard_events,
            job_manager=job_manager,
            mutation_policy=mutation_policy,
        ),
        infrastructure=infrastructure,
        progress_events=progress_events,
        dashboard_events=dashboard_events,
        job_manager=job_manager,
    )


def build_stage1_use_cases(
    infrastructure: InfrastructureBundle,
    *,
    progress_events: ProgressEventHub | None = None,
    dashboard_events: InMemoryDashboardEventHub | None = None,
    job_manager: JobManager | None = None,
    mutation_policy: CampaignMutationPolicy | None = None,
) -> Stage1UseCases:
    progress_events = progress_events or InMemoryProgressEventHub()
    dashboard_events = dashboard_events or InMemoryDashboardEventHub()
    progress_tracker_factory = StreamingProgressTrackerFactory(progress_events)
    mutation_policy = mutation_policy or _build_campaign_mutation_policy(infrastructure)

    if job_manager is None:
        processing_pipeline = build_processing_pipeline(infrastructure)
        job_manager = _build_local_job_manager(
            infrastructure,
            processing_pipeline,
            progress_events,
            dashboard_events,
        )

    guarded_infrastructure = replace(
        infrastructure,
        campaign_repository=MutationGuardingCampaignRepository(
            infrastructure.campaign_repository,
            mutation_policy,
        ),
    )
    return wire_stage1_use_cases(
        guarded_infrastructure,
        progress_tracker_factory=progress_tracker_factory,
        job_manager=job_manager,
        mutation_policy=mutation_policy,
    )


def _build_campaign_mutation_policy(
    infrastructure: InfrastructureBundle,
) -> CampaignMutationPolicy:
    guard = LocalCampaignMutationGuard(_job_lock_root(infrastructure.settings))
    return CampaignMutationPolicy(infrastructure.job_repository, guard)


def _build_local_job_manager(
    infrastructure: InfrastructureBundle,
    processing_pipeline: ExecuteQueuedProcessingJob,
    progress_events: ProgressEventHub,
    dashboard_events: InMemoryDashboardEventHub,
) -> LocalJobManager:
    return LocalJobManager(
        infrastructure.settings,
        processing_pipeline,
        infrastructure.job_repository,
        infrastructure.clock,
        lock_root=_job_lock_root(infrastructure.settings),
        progress_events=progress_events,
        dashboard_events=dashboard_events,
        transient_audio_cleaner=infrastructure.transient_audio_cleaner,
        review_submission_repository=(
            infrastructure.speaker_review_submission_repository
        ),
    )


def _job_lock_root(settings: NoteKeeperSettings) -> Path:
    sqlite_path = settings.sqlite_path.resolve(strict=False)
    return sqlite_path.parent / f".{sqlite_path.name}.locks"


def _recent_messages(
    use_cases: Stage1UseCases,
    campaign_id: str | None,
) -> tuple[str, ...]:
    if campaign_id is None:
        return ()

    try:
        jobs = use_cases.list_jobs_for_campaign.execute(
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


__all__ = ["NoteKeeperRuntime", "build_runtime", "build_stage1_use_cases"]
