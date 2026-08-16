"""Composition root for isolated processing workers."""

from dataclasses import dataclass
from multiprocessing.connection import Connection

from notekeeper.application import (
    DashboardChangedEvent,
    DashboardRefreshScope,
    RunProcessingJobCommand,
)
from notekeeper.application.errors import PortExecutionError
from notekeeper.domain import ProcessingJobId, WorkspaceId
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
        pipeline = build_processing_pipeline(self.services, self.repositories)
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
        runtime = build_worker_runtime(settings, writer=writer)
        pipeline = build_processing_pipeline(
            runtime.services,
            runtime.repositories,
            progress_tracker_factory=StreamingProgressTrackerFactory(writer),
        )
        job = runtime.repositories.job_repository.get(ProcessingJobId(job_id))
        if job is None:
            raise PortExecutionError(f"processing job {job_id} was not found")
        campaign = runtime.repositories.campaign_repository.get(job.campaign_id)
        if campaign is None or campaign.workspace_id != WorkspaceId(workspace_id):
            raise PortExecutionError(
                "processing job does not belong to the requested workspace"
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


__all__ = ["WorkerRuntime", "build_worker_runtime", "execute_worker_process"]
