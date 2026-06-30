"""Get job status use case."""

from notekeeper.application.commands import GetJobStatusCommand
from notekeeper.application.ports import JobRepository
from notekeeper.application.results import GetJobStatusResult
from notekeeper.application.use_cases.utils import _require_job
from notekeeper.domain import ProcessingJobId


class GetJobStatus:
    def __init__(self, job_repository: JobRepository) -> None:
        self._job_repository = job_repository

    def execute(self, command: GetJobStatusCommand) -> GetJobStatusResult:
        job = _require_job(self._job_repository, ProcessingJobId(command.job_id))
        return GetJobStatusResult(job=job)
