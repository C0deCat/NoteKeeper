"""Progress outcomes that respect concurrent job cancellation."""

from collections.abc import Callable

from notekeeper.application.ports import ProgressTracker
from notekeeper.domain import JobStatus, ProcessingJob


def pause_or_cancel(progress: ProgressTracker, job: ProcessingJob) -> None:
    _complete_or_cancel(progress, job, progress.pause)


def complete_or_cancel(progress: ProgressTracker, job: ProcessingJob) -> None:
    _complete_or_cancel(progress, job, progress.complete)


def fail_or_cancel(progress: ProgressTracker, job: ProcessingJob) -> None:
    _complete_or_cancel(progress, job, progress.fail)


def _complete_or_cancel(
    progress: ProgressTracker,
    job: ProcessingJob,
    outcome: Callable[[], None],
) -> None:
    if job.status in {JobStatus.CANCELING, JobStatus.CANCELED}:
        progress.cancel()
        return
    outcome()


__all__ = ["complete_or_cancel", "fail_or_cancel", "pause_or_cancel"]

