"""Local queued-job manager backed by isolated operating-system processes."""

from __future__ import annotations

import json
import logging
import multiprocessing
import threading
import time
from collections import deque
from dataclasses import dataclass, replace
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Any

import psutil
from filelock import FileLock, Timeout

from notekeeper.application import (
    ProgressEvent,
    ProgressEventKind,
    RunProcessingJobCommand,
)
from notekeeper.application.errors import InvalidOperationError, PortExecutionError
from notekeeper.application.ports import (
    Clock,
    DashboardEventHub,
    JobManager,
    JobRepository,
    ProgressEventHub,
    SpeakerReviewSubmissionRepository,
    TransientAudioCleaner,
)
from notekeeper.application.use_cases.processing.progress import processing_stages
from notekeeper.domain import (
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
    ProgressBar,
)
from notekeeper.infrastructure.filesystem.utils import safe_name


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ExecutionCapacity:
    owner_lock: FileLock | None
    total_lock: FileLock | None
    gpu_lock: FileLock | None


@dataclass(slots=True)
class _ManagedExecution:
    job_id: ProcessingJobId
    thread: threading.Thread
    capacity: _ExecutionCapacity
    process: BaseProcess | None = None


class LocalJobManager(JobManager):
    def __init__(
        self,
        settings: Any,
        pipeline: Any,
        job_repository: JobRepository,
        clock: Clock,
        *,
        lock_root: str | Path,
        progress_events: ProgressEventHub | None = None,
        dashboard_events: DashboardEventHub | None = None,
        transient_audio_cleaner: TransientAudioCleaner | None = None,
        review_submission_repository: SpeakerReviewSubmissionRepository | None = None,
    ) -> None:
        self._settings = settings
        self._pipeline = pipeline
        self._job_repository = job_repository
        self._clock = clock
        self._progress_events = progress_events
        self._dashboard_events = dashboard_events
        self._transient_audio_cleaner = transient_audio_cleaner
        self._review_submission_repository = review_submission_repository
        self._lock_root = Path(lock_root)
        self._capacity_root = self._lock_root / "capacity"
        self._execution_root = self._lock_root / "executions"
        self._context = multiprocessing.get_context("spawn")
        self._pending: deque[ProcessingJobId] = deque()
        self._pending_ids: set[str] = set()
        self._executions: dict[str, _ManagedExecution] = {}
        self._terminal_operations: set[str] = set()
        self._cancel_requests: set[str] = set()
        self._condition = threading.Condition(threading.RLock())
        self._dispatcher: threading.Thread | None = None
        self._stopping = False
        self._recover_persisted = False

    def start(self, *, recover_queued: bool = True) -> None:
        with self._condition:
            if self._dispatcher is not None and self._dispatcher.is_alive():
                if recover_queued:
                    self._recover_persisted = True
                    self._recover_queued_locked()
                    self._condition.notify_all()
                return
            self._stopping = False
            self._recover_persisted = recover_queued
            if recover_queued:
                self._recover_queued_locked()
            self._dispatcher = threading.Thread(
                target=self._dispatch_loop,
                name="notekeeper-job-dispatcher",
                daemon=True,
            )
            self._dispatcher.start()

    def enqueue(self, job_id: ProcessingJobId) -> None:
        self.start(recover_queued=False)
        key = str(job_id)
        with self._condition:
            if self._stopping:
                raise PortExecutionError("job manager is shutting down")
            if key not in self._pending_ids:
                self._pending.append(job_id)
                self._pending_ids.add(key)
            self._condition.notify_all()

    def request_cancel(self, job_id: ProcessingJobId) -> None:
        key = str(job_id)
        with self._condition:
            if key in self._pending_ids:
                self._pending = deque(item for item in self._pending if item != job_id)
                self._pending_ids.discard(key)
            if key in self._cancel_requests:
                return
            current = self._job_repository.get(job_id)
            if current is None or current.status is not JobStatus.CANCELING:
                return
            self._cancel_requests.add(key)
        threading.Thread(
            target=self._stop_and_finalize_cancel,
            args=(job_id,),
            name=f"notekeeper-job-cancel-{job_id}",
            daemon=True,
        ).start()

    def wait_for_terminal(
        self,
        job_id: ProcessingJobId,
        *,
        poll_interval: float = 0.1,
    ) -> ProcessingJob:
        while True:
            job = self._job_repository.get(job_id)
            if job is None:
                raise PortExecutionError(f"processing job {job_id} disappeared")
            if job.status in {
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELED,
                JobStatus.WAITING_FOR_REVIEW,
            }:
                with self._condition:
                    if str(job_id) not in self._executions:
                        return job
                    self._condition.wait(timeout=poll_interval)
                continue
            time.sleep(poll_interval)

    def shutdown(self) -> None:
        with self._condition:
            self._stopping = True
            self._pending.clear()
            self._pending_ids.clear()
            executions = tuple(self._executions.values())
            dispatcher = self._dispatcher
            self._condition.notify_all()
        for execution in executions:
            process = execution.process
            if process is not None and process.pid is not None and process.is_alive():
                _terminate_process_tree(process.pid)
        for execution in executions:
            execution.thread.join(timeout=10)
        if dispatcher is not None and dispatcher is not threading.current_thread():
            dispatcher.join(timeout=5)

    def _dispatch_loop(self) -> None:
        last_recovery = 0.0
        while True:
            try:
                with self._condition:
                    if self._stopping:
                        return
                    now = time.monotonic()
                    if self._recover_persisted and now - last_recovery >= 1.0:
                        self._recover_stale_executions_locked()
                        self._recover_queued_locked()
                        last_recovery = now
                    dispatched = self._dispatch_available_locked()
                    if not dispatched:
                        self._condition.wait(timeout=0.25)
            except Exception:
                logger.exception("Job manager dispatcher iteration failed")
                time.sleep(0.25)

    def _recover_queued_locked(self) -> None:
        for job in self._job_repository.list_by_statuses((JobStatus.QUEUED,)):
            key = str(job.id)
            if key not in self._pending_ids:
                self._pending.append(job.id)
                self._pending_ids.add(key)

    def _recover_stale_executions_locked(self) -> None:
        for job in self._job_repository.list_by_statuses(
            (JobStatus.RUNNING, JobStatus.CANCELING),
        ):
            key = str(job.id)
            if key in self._executions:
                continue
            owner_lock = self._file_lock(self._owner_lock_path(job.id))
            try:
                owner_lock.acquire(timeout=0)
            except Timeout:
                continue
            try:
                if self._recorded_process_is_alive(job.id):
                    continue
                if job.status is JobStatus.CANCELING:
                    recovered = replace(
                        job,
                        status=JobStatus.CANCELED,
                        updated_at=self._clock.now(),
                    )
                else:
                    recovered = replace(
                        job,
                        status=JobStatus.FAILED,
                        updated_at=self._clock.now(),
                        error_message="processing worker ownership was lost",
                    )
                self._job_repository.save_if_status(recovered, job.status)
                if self._review_submission_repository is not None:
                    self._review_submission_repository.delete(job.id)
                self._delete_execution_metadata(job.id)
            finally:
                owner_lock.release()

    def _dispatch_available_locked(self) -> bool:
        dispatched = False
        for _ in range(len(self._pending)):
            job_id = self._pending.popleft()
            key = str(job_id)
            if key in self._executions:
                self._pending.append(job_id)
                continue
            job = self._job_repository.get(job_id)
            if job is None or job.status is not JobStatus.QUEUED:
                self._pending_ids.discard(key)
                continue
            capacity = self._try_acquire_capacity(job)
            if capacity is None:
                self._pending.append(job_id)
                continue
            self._pending_ids.discard(key)
            thread = threading.Thread(
                target=self._execute_managed,
                args=(job_id,),
                name=f"notekeeper-job-monitor-{job_id}",
                daemon=True,
            )
            self._executions[key] = _ManagedExecution(
                job_id=job_id,
                thread=thread,
                capacity=capacity,
            )
            thread.start()
            dispatched = True
        return dispatched

    def _try_acquire_capacity(
        self,
        job: ProcessingJob,
    ) -> _ExecutionCapacity | None:
        self._capacity_root.mkdir(parents=True, exist_ok=True)
        owner_lock = self._file_lock(self._owner_lock_path(job.id))
        try:
            owner_lock.acquire(timeout=0)
        except Timeout:
            return None
        total_lock = self._try_acquire_slot(
            "total",
            self._settings.max_concurrent_jobs,
        )
        if total_lock is None:
            owner_lock.release()
            return None
        gpu_lock = None
        if self._requires_gpu(job):
            gpu_lock = self._try_acquire_slot(
                "gpu",
                self._settings.max_concurrent_gpu_jobs,
            )
            if gpu_lock is None:
                total_lock.release()
                owner_lock.release()
                return None
        return _ExecutionCapacity(
            owner_lock=owner_lock,
            total_lock=total_lock,
            gpu_lock=gpu_lock,
        )

    def _try_acquire_slot(self, kind: str, count: int) -> FileLock | None:
        for index in range(count):
            lock = self._file_lock(
                self._capacity_root / f"{kind}-{index}.lock",
            )
            try:
                lock.acquire(timeout=0)
            except Timeout:
                continue
            return lock
        return None

    def _requires_gpu(self, job: ProcessingJob) -> bool:
        return (
            job.transcript_id is None
            and str(self._settings.whisperx_device).lower().startswith("cuda")
        )

    def _execute_managed(self, job_id: ProcessingJobId) -> None:
        key = str(job_id)
        job_before_execution = self._job_repository.get(job_id)
        try:
            self._pipeline.start(RunProcessingJobCommand(job_id=key))
            self._run_child(job_id)
        except InvalidOperationError:
            return
        except Exception as exc:
            logger.exception("Queued processing job failed job_id=%s", job_id)
            self._fail_or_cancel(job_id, exc)
        finally:
            with self._condition:
                execution = self._executions.get(key)
            if execution is not None:
                self._release_execution_slots(execution.capacity)
            self._delete_execution_metadata(job_id)
            if self._transient_audio_cleaner is not None and job_before_execution:
                try:
                    self._transient_audio_cleaner.clean(
                        job_before_execution.campaign_id,
                        job_id,
                    )
                except Exception:
                    logger.exception(
                        "Could not clean parent-side transient audio job_id=%s",
                        job_id,
                    )
            if execution is not None:
                self._release_owner(execution.capacity)
            with self._condition:
                current = self._executions.get(key)
                if current is execution:
                    self._executions.pop(key, None)
                self._terminal_operations.discard(key)
                self._condition.notify_all()

    def _run_child(self, job_id: ProcessingJobId) -> None:
        result_reader, result_writer = self._context.Pipe(duplex=False)
        process = self._context.Process(
            target=_execute_job,
            args=(self._settings, str(job_id), result_writer),
            name=f"notekeeper-job-{job_id}",
        )
        key = str(job_id)
        with self._condition:
            execution = self._executions[key]
            execution.process = process
        try:
            process.start()
            self._write_execution_metadata(job_id, process.pid)
            result_writer.close()
            message = None
            while process.is_alive() or result_reader.poll():
                if not result_reader.poll(0.1):
                    continue
                kind, payload = result_reader.recv()
                if kind == "progress":
                    if payload.kind.is_terminal:
                        with self._condition:
                            self._terminal_operations.add(key)
                    if self._progress_events is not None:
                        self._progress_events.publish(payload)
                    continue
                if kind == "dashboard":
                    if self._dashboard_events is not None:
                        self._dashboard_events.publish(payload)
                    continue
                if kind == "resource_released":
                    if payload == "gpu":
                        self._release_gpu_capacity(job_id)
                    else:
                        logger.warning(
                            "Worker released unknown resource job_id=%s resource=%s",
                            job_id,
                            payload,
                        )
                    continue
                message = (kind, payload)
            process.join()
            if message is None:
                job = self._job_repository.get(job_id)
                if job is not None and job.status in {
                    JobStatus.CANCELING,
                    JobStatus.CANCELED,
                }:
                    self._finalize_cancel(job_id)
                    self._publish_terminal(job_id, ProgressEventKind.CANCELED)
                    return
                self._publish_terminal(job_id, ProgressEventKind.FAILED)
                raise PortExecutionError(
                    f"processing job process exited with code {process.exitcode}"
                )
            kind, payload = message
            if kind == "result":
                current = self._job_repository.get(job_id)
                if current is not None and current.status is JobStatus.CANCELING:
                    self._finalize_cancel(job_id)
                    self._publish_terminal(job_id, ProgressEventKind.CANCELED)
                return
            if kind != "result":
                self._publish_terminal(job_id, ProgressEventKind.FAILED)
                raise PortExecutionError(str(payload))
        except EOFError:
            self._publish_terminal(job_id, ProgressEventKind.FAILED)
            raise PortExecutionError("processing job process closed unexpectedly")
        finally:
            result_reader.close()
            result_writer.close()

    def _fail_or_cancel(self, job_id: ProcessingJobId, error: Exception) -> None:
        current = self._job_repository.get(job_id)
        if current is None:
            return
        if current.status is JobStatus.CANCELING:
            self._finalize_cancel(job_id)
            return
        if current.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
            return
        failed = replace(
            current,
            status=JobStatus.FAILED,
            updated_at=self._clock.now(),
            error_message=str(error).strip() or type(error).__name__,
        )
        if self._job_repository.save_if_status(failed, current.status):
            if self._review_submission_repository is not None:
                self._review_submission_repository.delete(job_id)

    def _finalize_cancel(self, job_id: ProcessingJobId) -> None:
        current = self._job_repository.get(job_id)
        if current is None or current.status is not JobStatus.CANCELING:
            return
        canceled = replace(
            current,
            status=JobStatus.CANCELED,
            updated_at=self._clock.now(),
        )
        if self._job_repository.save_if_status(canceled, JobStatus.CANCELING):
            if self._review_submission_repository is not None:
                self._review_submission_repository.delete(job_id)

    def _publish_terminal(
        self,
        job_id: ProcessingJobId,
        kind: ProgressEventKind,
    ) -> None:
        if self._progress_events is None:
            return
        operation_id = str(job_id)
        with self._condition:
            if operation_id in self._terminal_operations:
                return
            self._terminal_operations.add(operation_id)
        latest = self._progress_events.latest(operation_id)
        if latest is not None:
            event = ProgressEvent(
                operation_id=operation_id,
                stage_index=latest.stage_index,
                stage_count=latest.stage_count,
                timing_available=latest.timing_available,
                kind=kind,
                progress=latest.progress,
            )
        else:
            stages = processing_stages(
                alignment_enabled=self._settings.whisperx_alignment_enabled,
                diarization_enabled=self._settings.whisperx_diarization_enabled,
            )
            event = ProgressEvent(
                operation_id=operation_id,
                stage_index=1,
                stage_count=len(stages),
                timing_available=False,
                kind=kind,
                progress=ProgressBar(stage=stages[0].value),
            )
        self._progress_events.publish(event)

    def _metadata_path(self, job_id: ProcessingJobId) -> Path:
        job_name = safe_name(str(job_id), "job_id")
        return self._execution_root / f"{job_name}.json"

    def _owner_lock_path(self, job_id: ProcessingJobId) -> Path:
        self._execution_root.mkdir(parents=True, exist_ok=True)
        job_name = safe_name(str(job_id), "job_id")
        return self._execution_root / f"{job_name}.owner.lock"

    def _write_execution_metadata(
        self,
        job_id: ProcessingJobId,
        pid: int | None,
    ) -> None:
        if pid is None:
            return
        self._execution_root.mkdir(parents=True, exist_ok=True)
        create_time = psutil.Process(pid).create_time()
        self._metadata_path(job_id).write_text(
            json.dumps({"pid": pid, "create_time": create_time}),
            encoding="utf-8",
        )

    def _terminate_recorded_process(self, job_id: ProcessingJobId) -> bool:
        path = self._metadata_path(job_id)
        if not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            process = psutil.Process(int(payload["pid"]))
            if process.create_time() != float(payload["create_time"]):
                return False
            _terminate_process_tree(process.pid)
            return not process.is_running()
        except psutil.NoSuchProcess:
            return True
        except (OSError, ValueError, KeyError, json.JSONDecodeError, psutil.Error):
            return False

    def _recorded_process_is_alive(self, job_id: ProcessingJobId) -> bool:
        path = self._metadata_path(job_id)
        if not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            process = psutil.Process(int(payload["pid"]))
            return (
                process.is_running()
                and process.create_time() == float(payload["create_time"])
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError, psutil.Error):
            return False

    def _stop_and_finalize_cancel(self, job_id: ProcessingJobId) -> None:
        key = str(job_id)
        try:
            while True:
                current = self._job_repository.get(job_id)
                if current is None or current.status is not JobStatus.CANCELING:
                    return
                with self._condition:
                    execution = self._executions.get(key)
                process = execution.process if execution is not None else None
                if process is not None:
                    if process.pid is not None and process.is_alive():
                        _terminate_process_tree(process.pid)
                        process.join(timeout=5)
                    if not process.is_alive():
                        self._finalize_cancel(job_id)
                        return
                elif self._terminate_recorded_process(job_id):
                    self._finalize_cancel(job_id)
                    return
                elif not self._owner_is_active(job_id):
                    self._finalize_cancel(job_id)
                    return
                time.sleep(0.1)
        finally:
            with self._condition:
                self._cancel_requests.discard(key)
                self._condition.notify_all()

    def _owner_is_active(self, job_id: ProcessingJobId) -> bool:
        owner_lock = self._file_lock(self._owner_lock_path(job_id))
        try:
            owner_lock.acquire(timeout=0)
        except Timeout:
            return True
        owner_lock.release()
        return False

    @staticmethod
    def _file_lock(path: str | Path) -> FileLock:
        return FileLock(path, thread_local=False)

    def _release_gpu_capacity(self, job_id: ProcessingJobId) -> None:
        with self._condition:
            execution = self._executions.get(str(job_id))
            if execution is None:
                return
            gpu_lock = execution.capacity.gpu_lock
            execution.capacity.gpu_lock = None
            if gpu_lock is not None:
                gpu_lock.release()
                self._condition.notify_all()

    @staticmethod
    def _release_capacity(capacity: _ExecutionCapacity) -> None:
        LocalJobManager._release_execution_slots(capacity)
        LocalJobManager._release_owner(capacity)

    @staticmethod
    def _release_execution_slots(capacity: _ExecutionCapacity) -> None:
        locks = (capacity.gpu_lock, capacity.total_lock)
        capacity.gpu_lock = None
        capacity.total_lock = None
        for lock in locks:
            if lock is not None:
                lock.release()

    @staticmethod
    def _release_owner(capacity: _ExecutionCapacity) -> None:
        owner_lock = capacity.owner_lock
        capacity.owner_lock = None
        if owner_lock is not None:
            owner_lock.release()

    def _delete_execution_metadata(self, job_id: ProcessingJobId) -> None:
        path = self._metadata_path(job_id)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not delete execution metadata job_id=%s", job_id)


def _execute_job(settings: Any, job_id: str, result_writer) -> None:
    from .process_message_writer import ProcessMessageWriter

    writer = ProcessMessageWriter(result_writer)
    try:
        from dataclasses import replace as dataclass_replace

        from .factory import build_infrastructure
        from .job_pipeline import build_processing_pipeline
        from notekeeper.infrastructure.runtime import (
            EventPublishingJobRepository,
            StreamingProgressTrackerFactory,
        )

        infrastructure = build_infrastructure(
            settings,
            on_gpu_phase_completed=lambda: writer.resource_released("gpu"),
        )
        infrastructure = dataclass_replace(
            infrastructure,
            job_repository=EventPublishingJobRepository(
                infrastructure.job_repository,
                writer,
            ),
        )
        pipeline = build_processing_pipeline(
            infrastructure,
            progress_tracker_factory=StreamingProgressTrackerFactory(writer),
        )
        result = pipeline.execute_running(
            RunProcessingJobCommand(job_id=job_id),
        )
        writer.result(result)
    except BaseException as exc:
        writer.error(f"{type(exc).__name__}: {exc}")
    finally:
        writer.close()


def _terminate_process_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    descendants = parent.children(recursive=True)
    try:
        parent.terminate()
    except psutil.NoSuchProcess:
        pass
    for process in descendants:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(descendants, timeout=3)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        parent.wait(timeout=3)
    except psutil.NoSuchProcess:
        return
    except psutil.TimeoutExpired:
        parent.kill()


__all__ = ["LocalJobManager"]
