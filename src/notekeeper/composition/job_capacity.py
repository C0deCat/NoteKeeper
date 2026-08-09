"""Cross-process capacity allocation for queued processing jobs."""

from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock, Timeout

from notekeeper.domain import ProcessingJob

from .process_execution_registry import ProcessExecutionRegistry


@dataclass(slots=True)
class ExecutionCapacity:
    owner_lock: FileLock | None
    total_lock: FileLock | None
    gpu_lock: FileLock | None


class JobCapacityPool:
    def __init__(
        self,
        root: str | Path,
        execution_registry: ProcessExecutionRegistry,
        *,
        total_slots: int,
        gpu_slots: int,
        device: str,
    ) -> None:
        self._root = Path(root)
        self._execution_registry = execution_registry
        self._total_slots = total_slots
        self._gpu_slots = gpu_slots
        self._device = device

    def try_acquire(self, job: ProcessingJob) -> ExecutionCapacity | None:
        self._root.mkdir(parents=True, exist_ok=True)
        owner_lock = self.file_lock(self._execution_registry.owner_lock_path(job.id))
        if not self._acquire(owner_lock):
            return None

        total_lock = self._try_acquire_slot("total", self._total_slots)
        if total_lock is None:
            owner_lock.release()
            return None

        gpu_lock = None
        if self.requires_gpu(job):
            gpu_lock = self._try_acquire_slot("gpu", self._gpu_slots)
            if gpu_lock is None:
                total_lock.release()
                owner_lock.release()
                return None
        return ExecutionCapacity(owner_lock, total_lock, gpu_lock)

    def requires_gpu(self, job: ProcessingJob) -> bool:
        return job.transcript_id is None and self._device.lower().startswith("cuda")

    def _try_acquire_slot(self, kind: str, count: int) -> FileLock | None:
        for index in range(count):
            lock = self.file_lock(self._root / f"{kind}-{index}.lock")
            if self._acquire(lock):
                return lock
        return None

    @staticmethod
    def _acquire(lock: FileLock) -> bool:
        try:
            lock.acquire(timeout=0)
        except Timeout:
            return False
        return True

    @staticmethod
    def file_lock(path: str | Path) -> FileLock:
        return FileLock(path, thread_local=False)

    @staticmethod
    def release(capacity: ExecutionCapacity) -> None:
        JobCapacityPool.release_execution_slots(capacity)
        JobCapacityPool.release_owner(capacity)

    @staticmethod
    def release_execution_slots(capacity: ExecutionCapacity) -> None:
        locks = (capacity.gpu_lock, capacity.total_lock)
        capacity.gpu_lock = None
        capacity.total_lock = None
        for lock in locks:
            if lock is not None:
                lock.release()

    @staticmethod
    def release_owner(capacity: ExecutionCapacity) -> None:
        owner_lock = capacity.owner_lock
        capacity.owner_lock = None
        if owner_lock is not None:
            owner_lock.release()


__all__ = ["ExecutionCapacity", "JobCapacityPool"]
