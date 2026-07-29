"""Run composed processing jobs in isolated operating-system processes."""

from __future__ import annotations

import logging
import multiprocessing
import threading
from multiprocessing.process import BaseProcess
from typing import Any

import psutil

from notekeeper.application import (
    ProgressEvent,
    ProgressEventKind,
    RunProcessingJobCommand,
    RunProcessingJobResult,
)
from notekeeper.application.errors import PortExecutionError
from notekeeper.application.ports import (
    JobProcessExecutor,
    JobRepository,
    ProgressEventHub,
    TransientAudioCleaner,
)
from notekeeper.application.use_cases.processing.progress import processing_stages
from notekeeper.domain import JobStatus, ProcessingJobId, ProgressBar


logger = logging.getLogger(__name__)


class LocalProcessJobExecutor(JobProcessExecutor):
    def __init__(
        self,
        settings: Any,
        job_repository: JobRepository,
        progress_events: ProgressEventHub | None = None,
        transient_audio_cleaner: TransientAudioCleaner | None = None,
    ) -> None:
        self._settings = settings
        self._job_repository = job_repository
        self._progress_events = progress_events
        self._transient_audio_cleaner = transient_audio_cleaner
        self._context = multiprocessing.get_context("spawn")
        self._processes: dict[str, BaseProcess] = {}
        self._terminal_operations: set[str] = set()
        self._lock = threading.Lock()

    def execute(self, job_id: ProcessingJobId) -> RunProcessingJobResult:
        job_before_execution = self._job_repository.get(job_id)
        result_reader, result_writer = self._context.Pipe(duplex=False)
        process = self._context.Process(
            target=_execute_job,
            args=(self._settings, str(job_id), result_writer),
            name=f"notekeeper-job-{job_id}",
        )
        key = str(job_id)
        with self._lock:
            if key in self._processes:
                raise PortExecutionError(f"processing job {job_id} is already running")
            self._processes[key] = process
        try:
            process.start()
            try:
                result_writer.close()
                message = None
                while process.is_alive() or result_reader.poll():
                    if not result_reader.poll(0.1):
                        continue
                    kind, payload = result_reader.recv()
                    if kind == "progress":
                        if payload.kind.is_terminal:
                            with self._lock:
                                self._terminal_operations.add(key)
                        if self._progress_events is not None:
                            self._progress_events.publish(payload)
                        continue
                    message = (kind, payload)
            except EOFError:
                pass
            process.join()
            if message is None:
                job = self._job_repository.get(job_id)
                if job is not None and job.status is JobStatus.CANCELED:
                    self._publish_terminal(job_id, ProgressEventKind.CANCELED)
                    return RunProcessingJobResult(
                        job=job,
                        transcript=None,
                        recap=None,
                        warnings=job.warnings,
                    )
                self._publish_terminal(job_id, ProgressEventKind.FAILED)
                raise PortExecutionError(
                    f"processing job process exited with code {process.exitcode}"
                )
            kind, payload = message
            if kind == "result":
                return payload
            self._publish_terminal(job_id, ProgressEventKind.FAILED)
            raise PortExecutionError(str(payload))
        finally:
            with self._lock:
                self._processes.pop(key, None)
                self._terminal_operations.discard(key)
            result_reader.close()
            result_writer.close()
            if (
                self._transient_audio_cleaner is not None
                and job_before_execution is not None
            ):
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

    def cancel(self, job_id: ProcessingJobId) -> None:
        with self._lock:
            process = self._processes.get(str(job_id))
        if process is None or process.pid is None or not process.is_alive():
            return
        _terminate_process_tree(process.pid)
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
        self._publish_terminal(job_id, ProgressEventKind.CANCELED)

    def _publish_terminal(
        self,
        job_id: ProcessingJobId,
        kind: ProgressEventKind,
    ) -> None:
        if self._progress_events is None:
            return
        operation_id = str(job_id)
        with self._lock:
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


def _execute_job(settings: Any, job_id: str, result_writer) -> None:
    from .process_message_writer import ProcessMessageWriter

    writer = ProcessMessageWriter(result_writer)
    try:
        from .factory import build_infrastructure
        from .job_pipeline import build_processing_pipeline
        from notekeeper.infrastructure.runtime import (
            StreamingProgressTrackerFactory,
        )

        infrastructure = build_infrastructure(settings)
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


__all__ = ["LocalProcessJobExecutor"]
