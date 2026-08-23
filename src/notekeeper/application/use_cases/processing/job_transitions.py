"""Atomic processing-job state transitions."""

from notekeeper.application.errors import InvalidOperationError
from notekeeper.application.ports import JobRepository
from notekeeper.application.use_cases.utils import require_job
from notekeeper.domain import JobStatus, ProcessingJob


def claim_queued_job(repository: JobRepository, running_job: ProcessingJob) -> None:
    if not repository.save_if_status(running_job, JobStatus.QUEUED):
        raise InvalidOperationError("processing job is no longer queued")


def save_terminal_job(
    repository: JobRepository,
    job: ProcessingJob,
) -> ProcessingJob:
    if repository.save_if_status(job, JobStatus.RUNNING):
        return job

    current = require_job(repository, job.id)
    if current.status in {JobStatus.CANCELING, JobStatus.CANCELED}:
        return current
    raise InvalidOperationError("processing job status changed during execution")


__all__ = ["claim_queued_job", "save_terminal_job"]
