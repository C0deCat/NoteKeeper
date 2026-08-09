"""Queue a pending processing job for asynchronous execution."""

from dataclasses import replace

from notekeeper.application.commands import QueueProcessingJobCommand
from notekeeper.application.errors import InvalidOperationError
from notekeeper.application.ports import Clock, JobManager, JobRepository
from notekeeper.application.results import QueueProcessingJobResult
from notekeeper.application.use_cases.utils import (
    CampaignMutationPolicy,
    require_job,
)
from notekeeper.domain import JobStatus, ProcessingJobId


class QueueProcessingJob:
    def __init__(
        self,
        job_repository: JobRepository,
        job_manager: JobManager,
        mutation_policy: CampaignMutationPolicy,
        clock: Clock,
    ) -> None:
        self._job_repository = job_repository
        self._job_manager = job_manager
        self._mutation_policy = mutation_policy
        self._clock = clock

    def execute(
        self,
        command: QueueProcessingJobCommand,
    ) -> QueueProcessingJobResult:
        job_id = ProcessingJobId(command.job_id)
        job = require_job(self._job_repository, job_id)
        with self._mutation_policy.queue_transition(job.campaign_id):
            job = require_job(self._job_repository, job_id)
            if job.status is not JobStatus.PENDING:
                raise InvalidOperationError("processing job must be pending")
            queued_job = replace(
                job,
                status=JobStatus.QUEUED,
                updated_at=self._clock.now(),
                warnings=(),
                error_message=None,
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
