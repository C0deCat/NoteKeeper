import multiprocessing
import threading
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from notekeeper.application import AccessContext, SYSTEM_SCOPE

from notekeeper.application import (
    ExecuteQueuedProcessingJob,
    InvalidOperationError,
    QueueProcessingJob,
    QueueProcessingJobCommand,
    RunProcessingJobCommand,
)
from notekeeper.application.use_cases.utils import (
    CampaignMutationPolicy,
    GuardedCampaignMutation,
    GuardedJobQueue,
)
from notekeeper.domain import (
    CampaignId,
    JobStatus,
    ProcessingJob,
    UserId,
    WorkspaceId,
    WorkspaceRole,
)
from notekeeper.infrastructure.runtime import LocalCampaignMutationGuard
from notekeeper.infrastructure.sqlite import SQLiteDatabase, SQLiteJobRepository


class _JobRepository:
    def __init__(self, job: ProcessingJob) -> None:
        self.job = job

    def get(self, job_id):
        return self.job if self.job.id == job_id else None

    def save_if_status(self, job, expected_status) -> bool:
        if self.job.status is not expected_status:
            return False
        self.job = job
        return True

    def has_for_campaign_with_statuses(self, campaign_id, statuses) -> bool:
        return self.job.campaign_id == campaign_id and self.job.status in statuses


class _CampaignRepository:
    def get(self, campaign_id):
        if campaign_id == CampaignId("campaign-1"):
            return SimpleNamespace(id=campaign_id)
        return None


def _access_context() -> AccessContext:
    return AccessContext(
        UserId("user-1"),
        WorkspaceId("workspace-1"),
        WorkspaceRole.OWNER,
    )


class _Guard:
    def __init__(self) -> None:
        self.active = False
        self.acquisitions = 0

    @contextmanager
    def acquire(self, campaign_id):
        assert campaign_id == CampaignId("campaign-1")
        self.acquisitions += 1
        self.active = True
        try:
            yield
        finally:
            self.active = False


class _Manager:
    def __init__(self, guard: _Guard, *, error: Exception | None = None) -> None:
        self.guard = guard
        self.error = error
        self.enqueued = []
        self.guard_was_active = False

    def enqueue(self, job_id) -> None:
        self.guard_was_active = self.guard.active
        if self.error is not None:
            raise self.error
        self.enqueued.append(job_id)

    def request_cancel(self, job_id) -> None:
        return None


class _Clock:
    def now(self):
        return datetime(2026, 1, 1) + timedelta(seconds=5)


def _job(status: JobStatus = JobStatus.PENDING) -> ProcessingJob:
    return ProcessingJob(
        id="job-1",
        campaign_id="campaign-1",
        audio_track_id="audio-1",
        status=status,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )


def test_queue_processing_job_persists_before_enqueue() -> None:
    repository = _JobRepository(_job())
    guard = _Guard()
    manager = _Manager(guard)
    use_case = QueueProcessingJob(
        repository,
        manager,
        _Clock(),
    )

    result = use_case.execute(QueueProcessingJobCommand(job_id="job-1"))

    assert result.job.status is JobStatus.QUEUED
    assert result.job.updated_at == _Clock().now()
    assert repository.job == result.job
    assert manager.enqueued == [result.job.id]


def test_guarded_job_queue_holds_one_policy_lock_through_enqueue() -> None:
    repository = _JobRepository(_job())
    guard = _Guard()
    manager = _Manager(guard)
    use_case = GuardedJobQueue(
        QueueProcessingJob(repository, manager, _Clock()),
        CampaignMutationPolicy(repository, guard),
        _CampaignRepository(),
        repository,
        _access_context(),
    )

    use_case.execute(QueueProcessingJobCommand(job_id="job-1"))

    assert manager.guard_was_active
    assert guard.acquisitions == 1
    assert not guard.active


def test_queue_processing_job_compensates_explicit_enqueue_failure() -> None:
    original = _job()
    repository = _JobRepository(original)
    guard = _Guard()
    use_case = QueueProcessingJob(
        repository,
        _Manager(guard, error=RuntimeError("broker unavailable")),
        _Clock(),
    )

    with pytest.raises(RuntimeError, match="broker unavailable"):
        use_case.execute(QueueProcessingJobCommand(job_id="job-1"))

    assert repository.job == original


def test_queue_processing_job_rejects_second_delivery_from_public_api() -> None:
    repository = _JobRepository(_job(JobStatus.QUEUED))
    guard = _Guard()
    use_case = QueueProcessingJob(
        repository,
        _Manager(guard),
        _Clock(),
    )

    with pytest.raises(InvalidOperationError, match="must be pending"):
        use_case.execute(QueueProcessingJobCommand(job_id="job-1"))


def test_execute_queued_job_claims_persisted_job_only_once() -> None:
    repository = _JobRepository(_job(JobStatus.QUEUED))
    executor = object.__new__(ExecuteQueuedProcessingJob)
    executor._job_repository = repository
    executor._clock = _Clock()
    command = RunProcessingJobCommand(job_id="job-1")

    claimed = executor.start(command)
    assert claimed.status is JobStatus.RUNNING

    with pytest.raises(InvalidOperationError, match="must be queued"):
        executor.start(command)


@pytest.mark.parametrize(
    "status",
    (
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.CANCELING,
        JobStatus.WAITING_FOR_REVIEW,
    ),
)
def test_campaign_mutation_policy_blocks_every_active_status(status) -> None:
    repository = _JobRepository(_job(status))
    policy = CampaignMutationPolicy(repository, _Guard())

    with pytest.raises(InvalidOperationError, match="cannot be changed"):
        with policy.mutation(CampaignId("campaign-1")):
            raise AssertionError("mutation must not run")


@pytest.mark.parametrize(
    "status",
    (
        JobStatus.PENDING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELED,
    ),
)
def test_campaign_mutation_policy_allows_non_active_statuses(status) -> None:
    repository = _JobRepository(_job(status))
    policy = CampaignMutationPolicy(repository, _Guard())

    with policy.mutation(CampaignId("campaign-1")):
        repository.job = replace(repository.job, error_message="mutated")

    assert repository.job.error_message == "mutated"


def test_guarded_campaign_mutation_rejects_before_delegate_side_effects() -> None:
    repository = _JobRepository(_job(JobStatus.RUNNING))
    delegate = SimpleNamespace(
        execute=lambda command: (_ for _ in ()).throw(
            AssertionError("delegate must not run")
        )
    )
    use_case = GuardedCampaignMutation(
        delegate,
        CampaignMutationPolicy(repository, _Guard()),
    )

    with pytest.raises(InvalidOperationError, match="cannot be changed"):
        use_case.execute(SimpleNamespace(campaign_id="campaign-1"))


def test_queue_transition_serializes_with_cross_process_campaign_mutation(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "notekeeper.sqlite3")
    database.initialize()
    repository = SQLiteJobRepository(database, SYSTEM_SCOPE)
    repository.save(_job())
    lock_root = tmp_path / "locks"
    context = multiprocessing.get_context("spawn")
    acquired = context.Event()
    release = context.Event()
    process = context.Process(
        target=_hold_campaign_guard,
        args=(str(lock_root), acquired, release),
    )
    process.start()
    finished = threading.Event()
    errors = []

    def queue_job() -> None:
        try:
            use_case = QueueProcessingJob(
                repository,
                _RecordingManager(),
                _Clock(),
            )
            policy = CampaignMutationPolicy(
                repository,
                LocalCampaignMutationGuard(lock_root),
            )
            GuardedJobQueue(
                use_case,
                policy,
                _CampaignRepository(),
                repository,
                _access_context(),
            ).execute(QueueProcessingJobCommand(job_id="job-1"))
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()

    thread = threading.Thread(target=queue_job)
    try:
        assert acquired.wait(timeout=5)
        thread.start()
        assert not finished.wait(timeout=0.2)
        release.set()
        assert finished.wait(timeout=5)
    finally:
        release.set()
        thread.join(timeout=5)
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)

    assert not errors
    assert repository.get("job-1").status is JobStatus.QUEUED
    policy = CampaignMutationPolicy(
        repository,
        LocalCampaignMutationGuard(lock_root),
    )
    with pytest.raises(InvalidOperationError, match="cannot be changed"):
        with policy.mutation(CampaignId("campaign-1")):
            raise AssertionError("mutation must not run")


class _RecordingManager:
    def enqueue(self, job_id) -> None:
        return None

    def request_cancel(self, job_id) -> None:
        return None


def _hold_campaign_guard(lock_root: str, acquired, release) -> None:
    guard = LocalCampaignMutationGuard(lock_root)
    with guard.acquire(CampaignId("campaign-1")):
        acquired.set()
        release.wait(timeout=5)
