"""Delete a processing job and its job-owned temporary artifacts."""

from notekeeper.application.commands import DeleteProcessingJobCommand
from notekeeper.application.errors import InvalidOperationError
from notekeeper.application.ports import JobCleaner, JobRepository
from notekeeper.application.results import DeleteProcessingJobResult
from notekeeper.application.use_cases.utils import _require_job
from notekeeper.domain import (
    DomainValidationError,
    ProcessingJobId,
    ensure_processing_job_can_be_deleted,
)


class DeleteProcessingJob:
    def __init__(self, job_repository: JobRepository, job_cleaner: JobCleaner) -> None:
        self._job_repository = job_repository
        self._job_cleaner = job_cleaner

    def execute(self, command: DeleteProcessingJobCommand) -> DeleteProcessingJobResult:
        job = _require_job(self._job_repository, ProcessingJobId(command.job_id))
        try:
            ensure_processing_job_can_be_deleted(job)
        except DomainValidationError as exc:
            raise InvalidOperationError(str(exc)) from exc
        deleted_ids = self._job_cleaner.clean(job.campaign_id, (job,))
        return DeleteProcessingJobResult(job_id=str(deleted_ids[0]))


__all__ = ["DeleteProcessingJob"]
