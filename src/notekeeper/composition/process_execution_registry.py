"""Persisted identity records for processing worker processes."""

import json
import logging
from pathlib import Path

import psutil

from notekeeper.domain import ProcessingJobId
from notekeeper.infrastructure.filesystem.utils import safe_name

from .process_tree import terminate_process_tree

logger = logging.getLogger(__name__)


class ProcessExecutionRegistry:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def owner_lock_path(self, job_id: ProcessingJobId) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        return self._root / f"{self._job_name(job_id)}.owner.lock"

    def write(self, job_id: ProcessingJobId, pid: int | None) -> None:
        if pid is None:
            return
        self._root.mkdir(parents=True, exist_ok=True)
        create_time = psutil.Process(pid).create_time()
        self._metadata_path(job_id).write_text(
            json.dumps({"pid": pid, "create_time": create_time}),
            encoding="utf-8",
        )

    def terminate(self, job_id: ProcessingJobId) -> bool:
        process = self._recorded_process(job_id)
        if process is None:
            return False
        try:
            terminate_process_tree(process.pid)
            return not process.is_running()
        except psutil.NoSuchProcess:
            return True

    def is_alive(self, job_id: ProcessingJobId) -> bool:
        process = self._recorded_process(job_id)
        return process is not None and process.is_running()

    def delete(self, job_id: ProcessingJobId) -> None:
        try:
            self._metadata_path(job_id).unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not delete execution metadata job_id=%s", job_id)

    def _recorded_process(self, job_id: ProcessingJobId) -> psutil.Process | None:
        path = self._metadata_path(job_id)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            process = psutil.Process(int(payload["pid"]))
            if process.create_time() == float(payload["create_time"]):
                return process
        except (OSError, ValueError, KeyError, json.JSONDecodeError, psutil.Error):
            pass
        return None

    def _metadata_path(self, job_id: ProcessingJobId) -> Path:
        return self._root / f"{self._job_name(job_id)}.json"

    @staticmethod
    def _job_name(job_id: ProcessingJobId) -> str:
        return safe_name(str(job_id), "job_id")


__all__ = ["ProcessExecutionRegistry"]
