"""Composition root for isolated processing workers."""

from dataclasses import dataclass, replace
from multiprocessing.connection import Connection

from notekeeper.application import (
    DashboardChangedEvent,
    DashboardRefreshScope,
    RunProcessingJobCommand,
)
from notekeeper.application.errors import PortExecutionError
from notekeeper.domain import ProcessingJobId, ProcessingSettingsSnapshot, WorkspaceId
from notekeeper.infrastructure.filesystem import SnapshotRecapGuidances
from notekeeper.infrastructure.runtime import StreamingProgressTrackerFactory
from notekeeper.infrastructure.runtime.jobs import ProcessMessageWriter

from .factory import LocalServices, build_local_services
from .job_pipeline import build_processing_pipeline
from .repositories import SystemRepositories
from .settings import NoteKeeperSettings


@dataclass(frozen=True, slots=True)
class WorkerRuntime:
    services: LocalServices
    repositories: SystemRepositories

    def execute(self, workspace_id: WorkspaceId, job_id: ProcessingJobId):
        job = self.repositories.job_repository.get(job_id)
        if job is None:
            raise PortExecutionError(f"processing job {job_id} was not found")
        campaign = self.repositories.campaign_repository.get(job.campaign_id)
        if campaign is None or campaign.workspace_id != workspace_id:
            raise PortExecutionError(
                "processing job does not belong to the requested workspace"
            )
        services = _services_for_job(self.services, job, writer=None)
        pipeline = build_processing_pipeline(services, services.repositories)
        return pipeline.execute_running(RunProcessingJobCommand(job_id=str(job_id)))


def build_worker_runtime(
    settings: NoteKeeperSettings,
    *,
    writer: ProcessMessageWriter | None = None,
) -> WorkerRuntime:
    services = build_local_services(
        settings,
        on_gpu_phase_completed=(
            (lambda: writer.resource_released("gpu")) if writer is not None else None
        ),
    )
    return WorkerRuntime(services, services.repositories)


def execute_worker_process(
    settings: NoteKeeperSettings,
    workspace_id: str,
    job_id: str,
    result_writer: Connection,
) -> None:
    writer = ProcessMessageWriter(result_writer)
    try:
        runtime = build_worker_runtime(settings)
        job = runtime.repositories.job_repository.get(ProcessingJobId(job_id))
        if job is None:
            raise PortExecutionError(f"processing job {job_id} was not found")
        campaign = runtime.repositories.campaign_repository.get(job.campaign_id)
        if campaign is None or campaign.workspace_id != WorkspaceId(workspace_id):
            raise PortExecutionError(
                "processing job does not belong to the requested workspace"
            )
        services = _services_for_job(runtime.services, job, writer=writer)
        pipeline = build_processing_pipeline(
            services,
            services.repositories,
            progress_tracker_factory=StreamingProgressTrackerFactory(writer),
        )
        result = pipeline.execute_running(RunProcessingJobCommand(job_id=job_id))
        writer.publish(
            DashboardChangedEvent(
                campaign_id=str(campaign.id),
                scope=DashboardRefreshScope.CAMPAIGN_CONTENT,
            )
        )
        writer.result(result)
    except BaseException as exc:
        writer.error(f"{type(exc).__name__}: {exc}")
    finally:
        writer.close()


def _services_for_job(
    base_services: LocalServices,
    job,
    *,
    writer: ProcessMessageWriter | None,
) -> LocalServices:
    snapshot = job.settings_snapshot or _snapshot_for_legacy_job(base_services, job)
    if job.settings_snapshot is None:
        job = replace(job, settings_snapshot=snapshot)
        if not base_services.repositories.job_repository.save_if_status(
            job,
            job.status,
        ):
            raise PortExecutionError(
                "processing job changed while its settings snapshot was initialized"
            )
    effective = base_services.settings.model_copy(
        update={
            "whisperx_model_name": snapshot.whisperx_model_name,
            "whisperx_language": snapshot.whisperx_language,
            "deepseek_model_name": snapshot.deepseek_model_name,
            "deepseek_temperature": snapshot.deepseek_temperature,
        }
    )
    services = build_local_services(
        effective,
        on_gpu_phase_completed=(
            (lambda: writer.resource_released("gpu")) if writer is not None else None
        ),
    )
    return replace(
        services,
        recap_guidances=SnapshotRecapGuidances(snapshot),
    )


def _snapshot_for_legacy_job(
    services: LocalServices,
    job,
) -> ProcessingSettingsSnapshot:
    campaign = services.repositories.campaign_repository.get(job.campaign_id)
    if campaign is None:
        raise PortExecutionError(f"campaign {job.campaign_id} was not found")
    override = services.workspace_settings_repository.get(campaign.workspace_id)
    return ProcessingSettingsSnapshot(
        whisperx_model_name=(
            override.whisperx_model_name
            if override is not None
            else services.settings.whisperx_model_name
        ),
        whisperx_language=(
            override.whisperx_language
            if override is not None
            else services.settings.whisperx_language
        ),
        deepseek_model_name=(
            override.deepseek_model_name
            if override is not None
            else services.settings.deepseek_model_name
        ),
        deepseek_temperature=(
            override.deepseek_temperature
            if override is not None
            else services.settings.deepseek_temperature
        ),
        chunk_recap_prompt=services.recap_guidances.get_chunk_recap_guidances(
            campaign.id
        ),
        combine_chunks_prompt=services.recap_guidances.get_combined_recap_guidances(
            campaign.id
        ),
    )


__all__ = ["WorkerRuntime", "build_worker_runtime", "execute_worker_process"]
