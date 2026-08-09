"""Business rules for processing-job lifecycle actions."""

from dataclasses import replace
from datetime import datetime

from ..enums import JobStatus
from ..errors import DomainValidationError
from ..models import ProcessingJob


def ensure_processing_job_can_be_deleted(job: ProcessingJob) -> None:
    if job.status in {
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.CANCELING,
    }:
        raise DomainValidationError("active processing job cannot be deleted")


def cancel_processing_job(job: ProcessingJob, *, canceled_at: datetime) -> ProcessingJob:
    if job.status in {JobStatus.QUEUED, JobStatus.WAITING_FOR_REVIEW}:
        return replace(job, status=JobStatus.CANCELED, updated_at=canceled_at)
    if job.status is JobStatus.RUNNING:
        return replace(job, status=JobStatus.CANCELING, updated_at=canceled_at)
    if job.status is JobStatus.CANCELING:
        return job
    raise DomainValidationError("only active processing job can be canceled")


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
