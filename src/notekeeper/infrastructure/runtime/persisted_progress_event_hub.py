"""Cross-runtime progress distribution backed by persisted snapshots."""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Condition, RLock, Thread

from notekeeper.application.ports import (
    ProgressEventListener,
    ProgressEventSnapshotStore,
    Unsubscribe,
)
from notekeeper.application.results import ProgressEvent

logger = logging.getLogger(__name__)


class PersistedProgressEventHub:
    def __init__(
        self,
        snapshot_store: ProgressEventSnapshotStore,
        *,
        poll_interval: float = 0.25,
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self._snapshot_store = snapshot_store
        self._poll_interval = poll_interval
        self._condition = Condition(RLock())
        self._listeners: dict[str, dict[int, ProgressEventListener]] = {}
        self._last_seen: dict[str, ProgressEvent | None] = {}
        self._local_latest: dict[str, ProgressEvent] = {}
        self._next_subscription_id = 0
        self._poller: Thread | None = None

    def publish(self, event: ProgressEvent) -> None:
        try:
            self._snapshot_store.save(event)
        except Exception:
            logger.exception(
                "Could not persist progress snapshot operation_id=%s",
                event.operation_id,
            )

        with self._condition:
            if event.kind.is_terminal:
                self._local_latest.pop(event.operation_id, None)
            else:
                self._local_latest[event.operation_id] = event
            self._last_seen[event.operation_id] = event
            listeners = tuple(
                self._listeners.get(event.operation_id, {}).values(),
            )
            self._condition.notify_all()

        for listener in listeners:
            self._notify(listener, event)

    def subscribe(
        self,
        operation_id: str,
        listener: ProgressEventListener,
        *,
        replay_latest: bool = True,
    ) -> Unsubscribe:
        if not operation_id.strip():
            raise ValueError("operation_id must not be empty")
        loaded, snapshot = self._load_snapshot(operation_id)
        with self._condition:
            subscription_id = self._next_subscription_id
            self._next_subscription_id += 1
            listeners = self._listeners.setdefault(operation_id, {})
            listeners[subscription_id] = listener
            if loaded:
                self._last_seen[operation_id] = snapshot
            self._ensure_poller_locked()
            self._condition.notify_all()

        if replay_latest and snapshot is not None and not snapshot.kind.is_terminal:
            self._notify(listener, snapshot)

        def unsubscribe() -> None:
            with self._condition:
                operation_listeners = self._listeners.get(operation_id)
                if operation_listeners is None:
                    return
                operation_listeners.pop(subscription_id, None)
                if not operation_listeners:
                    self._listeners.pop(operation_id, None)
                    self._last_seen.pop(operation_id, None)
                self._condition.notify_all()

        return unsubscribe

    def latest(self, operation_id: str) -> ProgressEvent | None:
        loaded, snapshot = self._load_snapshot(operation_id)
        if loaded:
            return (
                snapshot
                if snapshot is not None and not snapshot.kind.is_terminal
                else None
            )
        with self._condition:
            return self._local_latest.get(operation_id)

    def _ensure_poller_locked(self) -> None:
        if self._poller is not None and self._poller.is_alive():
            return
        self._poller = Thread(
            target=self._poll,
            name="notekeeper-progress-snapshot-poller",
            daemon=True,
        )
        self._poller.start()

    def _poll(self) -> None:
        while True:
            with self._condition:
                if not self._listeners:
                    self._poller = None
                    return
                operation_ids = tuple(self._listeners)

            for operation_id in operation_ids:
                loaded, snapshot = self._load_snapshot(operation_id)
                if not loaded:
                    continue
                with self._condition:
                    if operation_id not in self._listeners:
                        continue
                    if self._last_seen.get(operation_id) == snapshot:
                        continue
                    self._last_seen[operation_id] = snapshot
                    listeners = tuple(self._listeners[operation_id].values())
                if snapshot is not None:
                    for listener in listeners:
                        self._notify(listener, snapshot)

            with self._condition:
                if not self._listeners:
                    self._poller = None
                    return
                self._condition.wait(timeout=self._poll_interval)

    def _load_snapshot(
        self,
        operation_id: str,
    ) -> tuple[bool, ProgressEvent | None]:
        try:
            return True, self._snapshot_store.get(operation_id)
        except Exception:
            logger.exception(
                "Could not read progress snapshot operation_id=%s",
                operation_id,
            )
            return False, None

    @staticmethod
    def _notify(
        listener: Callable[[ProgressEvent], None],
        event: ProgressEvent,
    ) -> None:
        try:
            listener(event)
        except Exception:
            logger.exception(
                "Progress subscriber failed for operation %s",
                event.operation_id,
            )


__all__ = ["PersistedProgressEventHub"]
