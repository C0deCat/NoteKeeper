"""Queue a pending processing job for asynchronous execution."""

from dataclasses import replace

from notekeeper.application.commands import QueueProcessingJobCommand
from notekeeper.application.errors import InvalidOperationError
from notekeeper.application.ports import Clock, JobManager, JobRepository
from notekeeper.application.results import QueueProcessingJobResult
from notekeeper.application.settings_service import SettingsService
from notekeeper.application.use_cases.utils import require_job
from notekeeper.domain import JobStatus, ProcessingJobId


class QueueProcessingJob:
    def __init__(
        self,
        job_repository: JobRepository,
        job_manager: JobManager,
        clock: Clock,
        settings_service: SettingsService | None = None,
    ) -> None:
        self._job_repository = job_repository
        self._job_manager = job_manager
        self._clock = clock
        self._settings_service = settings_service

    def execute(
        self,
        command: QueueProcessingJobCommand,
    ) -> QueueProcessingJobResult:
        job_id = ProcessingJobId(command.job_id)
        job = require_job(self._job_repository, job_id)
        if job.status is not JobStatus.PENDING:
            raise InvalidOperationError("processing job must be pending")
        snapshot = job.settings_snapshot
        if snapshot is None and self._settings_service is not None:
            snapshot = self._settings_service.snapshot_for_campaign(str(job.campaign_id))
        queued_job = replace(
            job,
            status=JobStatus.QUEUED,
            updated_at=self._clock.now(),
            warnings=(),
            error_message=None,
            settings_snapshot=snapshot,
        )
        if not self._job_repository.save_if_status(
            queued_job,
            JobStatus.PENDING,
        ):
            raise InvalidOperationError("processing job is no longer pending")

        try:
            self._job_manager.enqueue(job_id)
        except Exception:
            self._job_repository.save_if_status(job, JobStatus.QUEUED)
            raise
        return QueueProcessingJobResult(job=queued_job)


__all__ = ["QueueProcessingJob"]
