from datetime import datetime, timedelta

import pytest

from notekeeper.domain import (
    DomainValidationError,
    JobStatus,
    ProcessingJob,
    cancel_processing_job,
    ensure_processing_job_can_be_deleted,
    ensure_processing_job_can_be_restarted,
)


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


def test_processing_job_delete_rule_rejects_only_running() -> None:
    for status in JobStatus:
        if status is JobStatus.RUNNING:
            with pytest.raises(DomainValidationError, match="cannot be deleted"):
                ensure_processing_job_can_be_deleted(_job(status))
        else:
            ensure_processing_job_can_be_deleted(_job(status))


def test_cancel_processing_job_transitions_running_to_canceled() -> None:
    canceled_at = datetime(2026, 1, 1) + timedelta(seconds=5)
    result = cancel_processing_job(_job(JobStatus.RUNNING), canceled_at=canceled_at)
    assert result.status is JobStatus.CANCELED
    assert result.updated_at == canceled_at


def test_restart_rule_accepts_failed_and_canceled() -> None:
    ensure_processing_job_can_be_restarted(_job(JobStatus.FAILED))
    ensure_processing_job_can_be_restarted(_job(JobStatus.CANCELED))
    with pytest.raises(DomainValidationError, match="failed or canceled"):
        ensure_processing_job_can_be_restarted(_job(JobStatus.COMPLETED))
