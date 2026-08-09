"""Cancel a running processing job."""

from notekeeper.application.commands import CancelProcessingJobCommand
from notekeeper.application.errors import InvalidOperationError
from notekeeper.application.ports import (
    Clock,
    JobManager,
    JobRepository,
    SpeakerReviewSubmissionRepository,
)
from notekeeper.application.results import CancelProcessingJobResult
from notekeeper.application.use_cases.utils import require_job
from notekeeper.domain import (
    DomainValidationError,
    ProcessingJobId,
    cancel_processing_job,
)


class CancelProcessingJob:
    def __init__(
        self,
        job_repository: JobRepository,
        clock: Clock,
        job_manager: JobManager,
        submission_repository: SpeakerReviewSubmissionRepository | None = None,
    ) -> None:
        self._job_repository = job_repository
        self._clock = clock
        self._job_manager = job_manager
        self._submission_repository = submission_repository

    def execute(self, command: CancelProcessingJobCommand) -> CancelProcessingJobResult:
        job_id = ProcessingJobId(command.job_id)
        job = require_job(self._job_repository, job_id)
        try:
            canceled_job = cancel_processing_job(job, canceled_at=self._clock.now())
        except DomainValidationError as exc:
            raise InvalidOperationError(str(exc)) from exc
        if canceled_job is not job:
            if not self._job_repository.save_if_status(canceled_job, job.status):
                raise InvalidOperationError("processing job is no longer active")
        self._job_manager.request_cancel(job_id)
        if self._submission_repository is not None:
            self._submission_repository.delete(job_id)
        current = require_job(self._job_repository, job_id)
        return CancelProcessingJobResult(job=current)


__all__ = ["CancelProcessingJob"]
