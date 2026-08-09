import multiprocessing
import threading
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from filelock import FileLock

from notekeeper.composition.process_job_executor import (
    LocalJobManager,
    _ExecutionCapacity,
    _ManagedExecution,
)
from notekeeper.domain import JobStatus, ProcessingJob


class _Repository:
    def __init__(self, jobs=()) -> None:
        self.jobs = {job.id: job for job in jobs}

    def get(self, job_id):
        return self.jobs.get(job_id)

    def list_by_statuses(self, statuses):
        return tuple(job for job in self.jobs.values() if job.status in statuses)

    def save_if_status(self, job, expected_status) -> bool:
        current = self.jobs.get(job.id)
        if current is None or current.status is not expected_status:
            return False
        self.jobs[job.id] = job
        return True


class _Clock:
    def now(self):
        return datetime(2026, 1, 2)


def _settings(*, total=4, gpu=1, device="cpu"):
    return SimpleNamespace(
        max_concurrent_jobs=total,
        max_concurrent_gpu_jobs=gpu,
        whisperx_device=device,
        whisperx_alignment_enabled=False,
        whisperx_diarization_enabled=False,
    )


def _job(index: int, *, transcript=False, status=JobStatus.QUEUED):
    return ProcessingJob(
        id=f"job-{index}",
        campaign_id="campaign-1",
        audio_track_id=f"audio-{index}",
        status=status,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        transcript_id=(f"transcript-{index}" if transcript else None),
    )


def _manager(root: Path, settings, repository):
    return LocalJobManager(
        settings,
        SimpleNamespace(),
        repository,
        _Clock(),
        lock_root=root,
    )


def test_persisted_queue_recovery_is_fifo_and_deduplicated(tmp_path: Path) -> None:
    jobs = (_job(1), _job(2), _job(3))
    manager = _manager(tmp_path, _settings(), _Repository(jobs))

    with manager._condition:
        manager._recover_queued_locked()
        manager._recover_queued_locked()

    assert tuple(manager._pending) == tuple(job.id for job in jobs)


def test_capacity_slots_are_shared_by_multiple_managers(tmp_path: Path) -> None:
    jobs = tuple(_job(index) for index in range(1, 6))
    repository = _Repository(jobs)
    managers = [
        _manager(tmp_path, _settings(total=4), repository)
        for _ in jobs
    ]
    acquired = [
        manager._try_acquire_capacity(job)
        for manager, job in zip(managers[:4], jobs[:4], strict=True)
    ]
    try:
        assert all(locks is not None for locks in acquired)
        assert managers[4]._try_acquire_capacity(jobs[4]) is None
    finally:
        for capacity in acquired:
            if capacity is not None:
                LocalJobManager._release_capacity(capacity)


def test_capacity_slot_is_shared_across_processes(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    acquired = context.Event()
    release = context.Event()
    lock_path = tmp_path / "capacity" / "total-0.lock"
    process = context.Process(
        target=_hold_file_lock,
        args=(str(lock_path), acquired, release),
    )
    process.start()
    try:
        assert acquired.wait(timeout=5)
        job = _job(1)
        manager = _manager(tmp_path, _settings(total=1), _Repository((job,)))
        assert manager._try_acquire_capacity(job) is None
    finally:
        release.set()
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    assert process.exitcode == 0


def test_gpu_limit_does_not_block_cpu_or_review_continuation(tmp_path: Path) -> None:
    gpu_job = _job(1)
    second_gpu_job = _job(2)
    review_job = _job(3, transcript=True)
    repository = _Repository((gpu_job, second_gpu_job, review_job))
    settings = _settings(total=4, gpu=1, device="cuda")
    first = _manager(tmp_path, settings, repository)
    second = _manager(tmp_path, settings, repository)
    review = _manager(tmp_path, settings, repository)

    gpu_locks = first._try_acquire_capacity(gpu_job)
    assert gpu_locks is not None
    review_locks = None
    try:
        assert second._try_acquire_capacity(second_gpu_job) is None
        review_locks = review._try_acquire_capacity(review_job)
        assert review_locks is not None
    finally:
        if review_locks is not None:
            LocalJobManager._release_capacity(review_locks)
        LocalJobManager._release_capacity(gpu_locks)


def test_capacity_can_be_released_by_monitor_thread(tmp_path: Path) -> None:
    job = _job(1)
    repository = _Repository((job,))
    first = _manager(tmp_path, _settings(total=1), repository)
    second = _manager(tmp_path, _settings(total=1), repository)
    capacity = first._try_acquire_capacity(job)
    assert capacity is not None
    assert second._try_acquire_capacity(job) is None

    thread = threading.Thread(
        target=LocalJobManager._release_capacity,
        args=(capacity,),
    )
    thread.start()
    thread.join(timeout=5)

    reacquired = second._try_acquire_capacity(job)
    assert reacquired is not None
    LocalJobManager._release_capacity(reacquired)


def test_gpu_capacity_is_released_before_execution_finishes(tmp_path: Path) -> None:
    first_job = _job(1)
    second_job = _job(2)
    repository = _Repository((first_job, second_job))
    settings = _settings(total=4, gpu=1, device="cuda")
    first = _manager(tmp_path, settings, repository)
    second = _manager(tmp_path, settings, repository)
    capacity = first._try_acquire_capacity(first_job)
    assert capacity is not None
    first._executions[str(first_job.id)] = _ManagedExecution(
        job_id=first_job.id,
        thread=threading.current_thread(),
        capacity=capacity,
    )
    assert second._try_acquire_capacity(second_job) is None

    first._release_gpu_capacity(first_job.id)

    assert capacity.gpu_lock is None
    assert capacity.owner_lock is not None
    assert capacity.total_lock is not None
    second_capacity = second._try_acquire_capacity(second_job)
    assert second_capacity is not None
    LocalJobManager._release_capacity(second_capacity)
    LocalJobManager._release_capacity(capacity)


def test_enqueue_is_retained_while_previous_execution_cleans_up(
    tmp_path: Path,
) -> None:
    job = _job(1)
    manager = _manager(tmp_path, _settings(), _Repository((job,)))
    manager.start = lambda **_: None
    manager._executions[str(job.id)] = _ManagedExecution(
        job_id=job.id,
        thread=threading.current_thread(),
        capacity=_ExecutionCapacity(None, None, None),
    )

    manager.enqueue(job.id)
    with manager._condition:
        dispatched = manager._dispatch_available_locked()

    assert dispatched is False
    assert tuple(manager._pending) == (job.id,)


def test_recovery_finalizes_jobs_without_live_owner(tmp_path: Path) -> None:
    running = _job(1, status=JobStatus.RUNNING)
    canceling = _job(2, status=JobStatus.CANCELING)
    repository = _Repository((running, canceling))
    manager = _manager(tmp_path, _settings(), repository)

    with manager._condition:
        manager._recover_stale_executions_locked()

    assert repository.get(running.id).status is JobStatus.FAILED
    assert repository.get(canceling.id).status is JobStatus.CANCELED


def _hold_file_lock(lock_path: str, acquired, release) -> None:
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(path):
        acquired.set()
        release.wait(timeout=5)
