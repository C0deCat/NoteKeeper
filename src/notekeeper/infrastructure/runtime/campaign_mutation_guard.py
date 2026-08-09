"""Cross-process campaign mutation locks for a local NoteKeeper database."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from filelock import FileLock, Timeout

from notekeeper.application.errors import PortExecutionError
from notekeeper.application.ports import CampaignMutationGuard
from notekeeper.domain import CampaignId
from notekeeper.infrastructure.filesystem.utils import safe_name


class LocalCampaignMutationGuard(CampaignMutationGuard):
    def __init__(self, lock_root: str | Path, *, timeout_seconds: float = 5.0) -> None:
        self._lock_root = Path(lock_root)
        self._timeout_seconds = timeout_seconds
        self._locks: dict[str, FileLock] = {}
        self._locks_guard = RLock()

    @contextmanager
    def acquire(self, campaign_id: CampaignId) -> Generator[None, None, None]:
        self._lock_root.mkdir(parents=True, exist_ok=True)
        name = safe_name(str(campaign_id), "campaign_id")
        with self._locks_guard:
            lock = self._locks.setdefault(
                name,
                FileLock(
                    self._lock_root / f"campaign-{name}.lock",
                    timeout=self._timeout_seconds,
                ),
            )
        try:
            with lock:
                yield
        except Timeout as exc:
            raise PortExecutionError(
                f"campaign {campaign_id} is busy; try again"
            ) from exc


__all__ = ["LocalCampaignMutationGuard"]
