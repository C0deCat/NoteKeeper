import subprocess
import sys
from datetime import datetime
from types import SimpleNamespace

import psutil
import pytest

from notekeeper.application.errors import PortExecutionError
from notekeeper.composition.process_job_executor import (
    LocalProcessJobExecutor,
    _terminate_process_tree,
)
from notekeeper.domain import (
    AudioTrackId,
    CampaignId,
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
)


def test_process_executor_cleans_transient_audio_after_child_crash() -> None:
    job = ProcessingJob(
        id=ProcessingJobId("job-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
        status=JobStatus.RUNNING,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    repository = _JobRepository(job)
    cleaner = _TransientAudioCleaner()
    executor = LocalProcessJobExecutor(
        SimpleNamespace(),
        repository,
        transient_audio_cleaner=cleaner,
    )
    executor._context = _CrashedProcessContext()

    with pytest.raises(
        PortExecutionError,
        match="processing job process exited with code 7",
    ):
        executor.execute(job.id)

    assert cleaner.calls == [(job.campaign_id, job.id)]


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


class _EmptyReader:
    def poll(self, timeout: float | None = None) -> bool:
        return False

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
