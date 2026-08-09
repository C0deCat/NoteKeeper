"""Compatibility facade for queueing processing jobs."""

from notekeeper.application import (
    QueueProcessingJob,
    QueueProcessingJobCommand,
    QueueProcessingJobResult,
)


class IsolatedRunProcessingJob:
    def __init__(self, queue_processing_job: QueueProcessingJob) -> None:
        self._queue_processing_job = queue_processing_job

    def execute(
        self,
        command: QueueProcessingJobCommand,
    ) -> QueueProcessingJobResult:
        return self._queue_processing_job.execute(command)


__all__ = ["IsolatedRunProcessingJob"]
