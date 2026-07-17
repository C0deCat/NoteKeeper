"""Run composed processing jobs in isolated operating-system processes."""

from __future__ import annotations

import multiprocessing
import threading
from multiprocessing.process import BaseProcess
from typing import Any

import psutil

from notekeeper.application import RunProcessingJobCommand, RunProcessingJobResult
from notekeeper.application.errors import PortExecutionError
from notekeeper.application.ports import JobProcessExecutor, JobRepository
from notekeeper.domain import JobStatus, ProcessingJobId


class LocalProcessJobExecutor(JobProcessExecutor):
    def __init__(self, settings: Any, job_repository: JobRepository) -> None:
        self._settings = settings
        self._job_repository = job_repository
        self._context = multiprocessing.get_context("spawn")
        self._processes: dict[str, BaseProcess] = {}
        self._lock = threading.Lock()

    def execute(self, job_id: ProcessingJobId) -> RunProcessingJobResult:
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
                while process.is_alive() and not result_reader.poll(0.1):
                    pass
                message = result_reader.recv() if result_reader.poll(1) else None
            except EOFError:
                message = None
            process.join()
            if message is None:
                job = self._job_repository.get(job_id)
                if job is not None and job.status is JobStatus.CANCELED:
                    return RunProcessingJobResult(
                        job=job,
                        transcript=None,
                        recap=None,
                        warnings=job.warnings,
                    )
                raise PortExecutionError(
                    f"processing job process exited with code {process.exitcode}"
                )
            kind, payload = message
            if kind == "ok":
                return payload
            raise PortExecutionError(str(payload))
        finally:
            with self._lock:
                self._processes.pop(key, None)
            result_reader.close()
            result_writer.close()

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


def _execute_job(settings: Any, job_id: str, result_writer) -> None:
    try:
        from .factory import build_infrastructure
        from .job_pipeline import build_processing_pipeline

        infrastructure = build_infrastructure(settings)
        pipeline = build_processing_pipeline(infrastructure)
        result = pipeline.execute_running(
            RunProcessingJobCommand(job_id=job_id),
        )
        result_writer.send(("ok", result))
    except BaseException as exc:
        result_writer.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        result_writer.close()


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
