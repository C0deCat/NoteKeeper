"""Application-facing processing use case backed by an isolated process."""

from notekeeper.application import (
    RunProcessingJob,
    RunProcessingJobCommand,
    RunProcessingJobResult,
)
from notekeeper.application.ports import JobProcessExecutor
from notekeeper.domain import ProcessingJobId


class IsolatedRunProcessingJob(RunProcessingJob):
    def __init__(self, pipeline, executor: JobProcessExecutor) -> None:
        self._pipeline = pipeline
        self._executor = executor

    def execute(self, command: RunProcessingJobCommand) -> RunProcessingJobResult:
        running_job = self._pipeline.start(command)
        return self._executor.execute(running_job.id)


__all__ = ["IsolatedRunProcessingJob"]
