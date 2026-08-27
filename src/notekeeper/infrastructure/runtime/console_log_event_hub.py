"""Process-local console log event distribution."""

from __future__ import annotations

import logging
from threading import RLock

from notekeeper.application.ports import ConsoleLogEventListener, Unsubscribe
from notekeeper.application.results import ConsoleLogEvent

logger = logging.getLogger(__name__)


class InMemoryConsoleLogEventHub:
    """Thread-safe fan-out for console output captured from processing workers."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._listeners: dict[int, ConsoleLogEventListener] = {}
        self._next_subscription_id = 0

    def publish(self, event: ConsoleLogEvent) -> None:
        with self._lock:
            listeners = tuple(self._listeners.values())
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("Console log event subscriber failed")

    def subscribe(self, listener: ConsoleLogEventListener) -> Unsubscribe:
        with self._lock:
            subscription_id = self._next_subscription_id
            self._next_subscription_id += 1
            self._listeners[subscription_id] = listener

        def unsubscribe() -> None:
            with self._lock:
                self._listeners.pop(subscription_id, None)

        return unsubscribe


__all__ = ["InMemoryConsoleLogEventHub"]
