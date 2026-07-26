"""Business rules for processing-job lifecycle actions."""

from dataclasses import replace
from datetime import datetime

from ..enums import JobStatus
from ..errors import DomainValidationError
from ..models import ProcessingJob


def ensure_processing_job_can_be_deleted(job: ProcessingJob) -> None:
    if job.status is JobStatus.RUNNING:
        raise DomainValidationError("running processing job cannot be deleted")


def cancel_processing_job(job: ProcessingJob, *, canceled_at: datetime) -> ProcessingJob:
    if job.status is not JobStatus.RUNNING:
        raise DomainValidationError("only running processing job can be canceled")
    return replace(job, status=JobStatus.CANCELED, updated_at=canceled_at)


def ensure_processing_job_can_be_restarted(job: ProcessingJob) -> None:
    if job.status not in {JobStatus.FAILED, JobStatus.CANCELED}:
        raise DomainValidationError(
            "processing job must be failed or canceled to be restarted"
        )


__all__ = [
    "cancel_processing_job",
    "ensure_processing_job_can_be_deleted",
    "ensure_processing_job_can_be_restarted",
]
