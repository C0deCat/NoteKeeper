"""Cancel a running processing job."""

from notekeeper.application.commands import CancelProcessingJobCommand
from notekeeper.application.errors import InvalidOperationError
from notekeeper.application.ports import Clock, JobExecutionController, JobRepository
from notekeeper.application.results import CancelProcessingJobResult
from notekeeper.application.use_cases.utils import _require_job
from notekeeper.domain import (
    DomainValidationError,
    JobStatus,
    ProcessingJobId,
    cancel_processing_job,
)


class CancelProcessingJob:
    def __init__(
        self,
        job_repository: JobRepository,
        clock: Clock,
        execution_controller: JobExecutionController,
    ) -> None:
        self._job_repository = job_repository
        self._clock = clock
        self._execution_controller = execution_controller

    def execute(self, command: CancelProcessingJobCommand) -> CancelProcessingJobResult:
        job_id = ProcessingJobId(command.job_id)
        job = _require_job(self._job_repository, job_id)
        try:
            canceled_job = cancel_processing_job(job, canceled_at=self._clock.now())
        except DomainValidationError as exc:
            raise InvalidOperationError(str(exc)) from exc
        if not self._job_repository.save_if_status(canceled_job, JobStatus.RUNNING):
            raise InvalidOperationError("processing job is no longer running")
        self._execution_controller.cancel(job_id)
        return CancelProcessingJobResult(job=canceled_job)


__all__ = ["CancelProcessingJob"]
