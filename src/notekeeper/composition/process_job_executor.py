"""Local queued-job manager backed by isolated operating-system processes."""

from __future__ import annotations

import logging
import multiprocessing
import threading
import time
from collections import deque
from dataclasses import dataclass, replace
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path

from filelock import FileLock, Timeout

from notekeeper.application import (
    ExecuteQueuedProcessingJob,
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

from .job_capacity import ExecutionCapacity, JobCapacityPool
from .process_execution_registry import ProcessExecutionRegistry
from .process_tree import terminate_process_tree
from .settings import NoteKeeperSettings

logger = logging.getLogger(__name__)


_ExecutionCapacity = ExecutionCapacity


@dataclass(slots=True)
class _ManagedExecution:
    job_id: ProcessingJobId
    thread: threading.Thread
    capacity: _ExecutionCapacity
    process: BaseProcess | None = None


class LocalJobManager(JobManager):
    def __init__(
        self,
        settings: NoteKeeperSettings,
        pipeline: ExecuteQueuedProcessingJob,
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
        self._execution_registry = ProcessExecutionRegistry(
            self._lock_root / "executions"
        )
        self._capacity_pool = JobCapacityPool(
            self._lock_root / "capacity",
            self._execution_registry,
            total_slots=settings.max_concurrent_jobs,
            gpu_slots=settings.max_concurrent_gpu_jobs,
            device=settings.whisperx_device,
        )
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
                terminate_process_tree(process.pid)
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
        return self._capacity_pool.try_acquire(job)

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

    def _owner_lock_path(self, job_id: ProcessingJobId) -> Path:
        return self._execution_registry.owner_lock_path(job_id)

    def _write_execution_metadata(
        self,
        job_id: ProcessingJobId,
        pid: int | None,
    ) -> None:
        self._execution_registry.write(job_id, pid)

    def _terminate_recorded_process(self, job_id: ProcessingJobId) -> bool:
        return self._execution_registry.terminate(job_id)

    def _recorded_process_is_alive(self, job_id: ProcessingJobId) -> bool:
        return self._execution_registry.is_alive(job_id)

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
                        terminate_process_tree(process.pid)
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
        return JobCapacityPool.file_lock(path)

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
        JobCapacityPool.release(capacity)

    @staticmethod
    def _release_execution_slots(capacity: _ExecutionCapacity) -> None:
        JobCapacityPool.release_execution_slots(capacity)

    @staticmethod
    def _release_owner(capacity: _ExecutionCapacity) -> None:
        JobCapacityPool.release_owner(capacity)

    def _delete_execution_metadata(self, job_id: ProcessingJobId) -> None:
        self._execution_registry.delete(job_id)


def _execute_job(
    settings: NoteKeeperSettings,
    job_id: str,
    result_writer: Connection,
) -> None:
    from .process_message_writer import ProcessMessageWriter

    writer = ProcessMessageWriter(result_writer)
    try:
        from dataclasses import replace as dataclass_replace

        from notekeeper.infrastructure.runtime import (
            EventPublishingJobRepository,
            StreamingProgressTrackerFactory,
        )

        from .factory import build_infrastructure
        from .job_pipeline import build_processing_pipeline

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
    terminate_process_tree(pid)


__all__ = [
    "LocalJobManager",
    "_ExecutionCapacity",
    "_ManagedExecution",
    "_terminate_process_tree",
]
