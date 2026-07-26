"""Process-local progress event distribution."""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import RLock

from notekeeper.application.ports import ProgressEventListener, Unsubscribe
from notekeeper.application.results import ProgressEvent

logger = logging.getLogger(__name__)


class InMemoryProgressEventHub:
    """Thread-safe fan-out that retains only active operation snapshots."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._latest: dict[str, ProgressEvent] = {}
        self._listeners: dict[str, dict[int, ProgressEventListener]] = {}
        self._next_subscription_id = 0

    def publish(self, event: ProgressEvent) -> None:
        with self._lock:
            if not event.kind.is_terminal:
                self._latest[event.operation_id] = event
            listeners = tuple(
                self._listeners.get(event.operation_id, {}).values()
            )

        for listener in listeners:
            self._notify(listener, event)

        if event.kind.is_terminal:
            with self._lock:
                self._latest.pop(event.operation_id, None)

    def subscribe(
        self,
        operation_id: str,
        listener: ProgressEventListener,
        *,
        replay_latest: bool = True,
    ) -> Unsubscribe:
        if not operation_id.strip():
            raise ValueError("operation_id must not be empty")
        with self._lock:
            subscription_id = self._next_subscription_id
            self._next_subscription_id += 1
            listeners = self._listeners.setdefault(operation_id, {})
            listeners[subscription_id] = listener
            latest = self._latest.get(operation_id) if replay_latest else None

        if latest is not None:
            self._notify(listener, latest)

        def unsubscribe() -> None:
            with self._lock:
                listeners = self._listeners.get(operation_id)
                if listeners is None:
                    return
                listeners.pop(subscription_id, None)
                if not listeners:
                    self._listeners.pop(operation_id, None)

        return unsubscribe

    def latest(self, operation_id: str) -> ProgressEvent | None:
        with self._lock:
            return self._latest.get(operation_id)

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


__all__ = ["InMemoryProgressEventHub"]
