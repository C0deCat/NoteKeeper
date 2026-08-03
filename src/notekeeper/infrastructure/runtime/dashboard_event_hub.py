"""Process-local dashboard invalidation event distribution."""

from __future__ import annotations

import logging
from threading import RLock

from notekeeper.application.ports import (
    DashboardEventListener,
    Unsubscribe,
)
from notekeeper.application.results import DashboardChangedEvent

logger = logging.getLogger(__name__)


class InMemoryDashboardEventHub:
    """Thread-safe fan-out for dashboard invalidation events."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._listeners: dict[int, DashboardEventListener] = {}
        self._next_subscription_id = 0

    def publish(self, event: DashboardChangedEvent) -> None:
        with self._lock:
            listeners = tuple(self._listeners.values())
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("Dashboard event subscriber failed")

    def subscribe(self, listener: DashboardEventListener) -> Unsubscribe:
        with self._lock:
            subscription_id = self._next_subscription_id
            self._next_subscription_id += 1
            self._listeners[subscription_id] = listener

        def unsubscribe() -> None:
            with self._lock:
                self._listeners.pop(subscription_id, None)

        return unsubscribe


__all__ = ["InMemoryDashboardEventHub"]
