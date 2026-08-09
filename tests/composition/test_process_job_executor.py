import subprocess
import sys
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psutil

from notekeeper.application import (
    DashboardChangedEvent,
    DashboardRefreshScope,
    RunProcessingJobResult,
)
from notekeeper.composition.process_job_executor import (
    LocalJobManager,
    _ExecutionCapacity,
    _ManagedExecution,
    _terminate_process_tree,
)
from notekeeper.domain import (
    AudioTrackId,
    CampaignId,
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
)
from notekeeper.infrastructure.runtime import InMemoryDashboardEventHub


def test_job_manager_marks_job_failed_and_cleans_after_child_crash(
    tmp_path: Path,
) -> None:
    job = ProcessingJob(
        id=ProcessingJobId("job-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
        status=JobStatus.QUEUED,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    repository = _JobRepository(job)
    cleaner = _TransientAudioCleaner()
    manager = LocalJobManager(
        _settings(),
        _Pipeline(repository),
        repository,
        _Clock(),
        lock_root=tmp_path,
        transient_audio_cleaner=cleaner,
    )
    manager._context = _CrashedProcessContext()
    manager._write_execution_metadata = lambda *_: None
    manager._executions[str(job.id)] = _ManagedExecution(
        job_id=job.id,
        thread=threading.current_thread(),
        capacity=_ExecutionCapacity(None, None, None),
    )
    manager._execute_managed(job.id)

    assert cleaner.calls == [(job.campaign_id, job.id)]
    assert repository.get(job.id).status is JobStatus.FAILED


def test_job_manager_forwards_dashboard_events_from_child(tmp_path: Path) -> None:
    job = ProcessingJob(
        id=ProcessingJobId("job-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
        status=JobStatus.QUEUED,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    event = DashboardChangedEvent(
        campaign_id="campaign-1",
        scope=DashboardRefreshScope.CAMPAIGN_CONTENT,
    )
    result = RunProcessingJobResult(
        job=job,
        transcript=None,
        recap=None,
        warnings=(),
    )
    dashboard_events = InMemoryDashboardEventHub()
    received: list[DashboardChangedEvent] = []
    dashboard_events.subscribe(received.append)
    repository = _JobRepository(job)
    manager = LocalJobManager(
        _settings(),
        _Pipeline(repository),
        repository,
        _Clock(),
        lock_root=tmp_path,
        dashboard_events=dashboard_events,
    )
    manager._context = _MessageProcessContext(
        (("dashboard", event), ("result", result)),
    )
    manager._write_execution_metadata = lambda *_: None
    manager._executions[str(job.id)] = _ManagedExecution(
        job_id=job.id,
        thread=threading.current_thread(),
        capacity=_ExecutionCapacity(None, None, None),
    )

    manager._execute_managed(job.id)
    assert received == [event]


def test_job_manager_releases_gpu_on_worker_message(tmp_path: Path) -> None:
    job = ProcessingJob(
        id=ProcessingJobId("job-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
        status=JobStatus.QUEUED,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    result = RunProcessingJobResult(
        job=job,
        transcript=None,
        recap=None,
        warnings=(),
    )
    repository = _JobRepository(job)
    manager = LocalJobManager(
        _settings(device="cuda"),
        _Pipeline(repository),
        repository,
        _Clock(),
        lock_root=tmp_path,
    )
    manager._context = _MessageProcessContext(
        (("resource_released", "gpu"), ("result", result)),
    )
    manager._write_execution_metadata = lambda *_: None
    capacity = manager._try_acquire_capacity(job)
    assert capacity is not None and capacity.gpu_lock is not None
    manager._executions[str(job.id)] = _ManagedExecution(
        job_id=job.id,
        thread=threading.current_thread(),
        capacity=capacity,
    )

    with patch.object(
        manager,
        "_release_gpu_capacity",
        wraps=manager._release_gpu_capacity,
    ) as release_gpu:
        manager._execute_managed(job.id)

    release_gpu.assert_called_once_with(job.id)


def test_terminate_process_tree_stops_parent_and_child() -> None:
    script = (
        "import subprocess,sys,time; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        "print(child.pid, flush=True); time.sleep(60)"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert parent.stdout is not None
    child_pid = int(parent.stdout.readline().strip())
    try:
        _terminate_process_tree(parent.pid)
        parent.wait(timeout=5)
        assert not psutil.pid_exists(parent.pid)
        assert not psutil.pid_exists(child_pid)
    finally:
        for pid in (child_pid, parent.pid):
            try:
                psutil.Process(pid).kill()
            except psutil.NoSuchProcess:
                pass


class _JobRepository:
    def __init__(self, job: ProcessingJob) -> None:
        self._job = job

    def get(self, job_id: ProcessingJobId) -> ProcessingJob | None:
        return self._job if job_id == self._job.id else None

    def save_if_status(self, job, expected_status) -> bool:
        if self._job.status is not expected_status:
            return False
        self._job = job
        return True

    def list_by_statuses(self, statuses):
        return (self._job,) if self._job.status in statuses else ()


class _Pipeline:
    def __init__(self, repository: _JobRepository) -> None:
        self._repository = repository

    def start(self, command):
        job = self._repository.get(ProcessingJobId(command.job_id))
        running = replace(job, status=JobStatus.RUNNING)
        assert self._repository.save_if_status(running, JobStatus.QUEUED)
        return running


class _Clock:
    def now(self):
        return datetime(2026, 1, 2)


def _settings(*, device: str = "cpu"):
    return SimpleNamespace(
        max_concurrent_jobs=4,
        max_concurrent_gpu_jobs=1,
        whisperx_device=device,
        whisperx_alignment_enabled=False,
        whisperx_diarization_enabled=False,
    )


class _TransientAudioCleaner:
    def __init__(self) -> None:
        self.calls: list[tuple[CampaignId, ProcessingJobId]] = []

    def clean(
        self,
        campaign_id: CampaignId,
        job_id: ProcessingJobId,
    ) -> None:
        self.calls.append((campaign_id, job_id))

    def clean_stale(self) -> None:
        return None


class _CrashedProcessContext:
    def Pipe(self, *, duplex: bool):
        assert duplex is False
        return _EmptyReader(), _ClosedWriter()

    def Process(self, **kwargs):
        return _CrashedProcess()


class _MessageProcessContext:
    def __init__(self, messages) -> None:
        self._messages = messages

    def Pipe(self, *, duplex: bool):
        assert duplex is False
        return _MessageReader(self._messages), _ClosedWriter()

    def Process(self, **kwargs):
        return _SuccessfulProcess()


class _EmptyReader:
    def poll(self, timeout: float | None = None) -> bool:
        return False

    def close(self) -> None:
        return None


class _MessageReader:
    def __init__(self, messages) -> None:
        self._messages = list(messages)

    def poll(self, timeout: float | None = None) -> bool:
        return bool(self._messages)

    def recv(self):
        return self._messages.pop(0)

    def close(self) -> None:
        return None


class _ClosedWriter:
    def close(self) -> None:
        return None


class _CrashedProcess:
    pid = 123
    exitcode = 7

    def start(self) -> None:
        return None

    def is_alive(self) -> bool:
        return False

    def join(self, timeout: float | None = None) -> None:
        return None


class _SuccessfulProcess(_CrashedProcess):
    exitcode = 0
