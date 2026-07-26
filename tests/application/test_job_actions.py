from datetime import datetime, timedelta

import pytest

from notekeeper.application import (
    CancelProcessingJob,
    CancelProcessingJobCommand,
    DeleteProcessingJob,
    DeleteProcessingJobCommand,
    InvalidOperationError,
)
from notekeeper.domain import JobStatus, ProcessingJob


class _Jobs:
    def __init__(self, job: ProcessingJob) -> None:
        self.job = job

    def get(self, job_id):
        return self.job if self.job is not None and self.job.id == job_id else None

    def save_if_status(self, job, expected_status) -> bool:
        if self.job is None or self.job.status is not expected_status:
            return False
        self.job = job
        return True


class _Cleaner:
    def __init__(self, jobs: _Jobs) -> None:
        self.jobs = jobs
        self.calls = []

    def clean(self, campaign_id, jobs):
        self.calls.append((campaign_id, jobs))
        self.jobs.job = None
        return tuple(job.id for job in jobs)


class _Clock:
    def now(self):
        return datetime(2026, 1, 1) + timedelta(seconds=10)


class _Controller:
    def __init__(self) -> None:
        self.canceled = []

    def cancel(self, job_id) -> None:
        self.canceled.append(job_id)


def _job(status: JobStatus) -> ProcessingJob:
    now = datetime(2026, 1, 1)
    return ProcessingJob(
        id="job-1",
        campaign_id="campaign-1",
        audio_track_id="audio-1",
        status=status,
        created_at=now,
        updated_at=now,
    )


def test_delete_processing_job_removes_non_running_job() -> None:
    jobs = _Jobs(_job(JobStatus.COMPLETED))
    cleaner = _Cleaner(jobs)
    result = DeleteProcessingJob(jobs, cleaner).execute(
        DeleteProcessingJobCommand(job_id="job-1")
    )
    assert result.job_id == "job-1"
    assert jobs.job is None


def test_delete_processing_job_rejects_running_job() -> None:
    jobs = _Jobs(_job(JobStatus.RUNNING))
    with pytest.raises(InvalidOperationError, match="cannot be deleted"):
        DeleteProcessingJob(jobs, _Cleaner(jobs)).execute(
            DeleteProcessingJobCommand(job_id="job-1")
        )


def test_cancel_processing_job_persists_status_before_stopping_process() -> None:
    jobs = _Jobs(_job(JobStatus.RUNNING))
    controller = _Controller()
    result = CancelProcessingJob(jobs, _Clock(), controller).execute(
        CancelProcessingJobCommand(job_id="job-1")
    )
    assert result.job.status is JobStatus.CANCELED
    assert jobs.job == result.job
    assert controller.canceled == [result.job.id]


def test_cancel_processing_job_rejects_non_running_job() -> None:
    jobs = _Jobs(_job(JobStatus.CANCELED))
    with pytest.raises(InvalidOperationError, match="only running"):
        CancelProcessingJob(jobs, _Clock(), _Controller()).execute(
            CancelProcessingJobCommand(job_id="job-1")
        )
