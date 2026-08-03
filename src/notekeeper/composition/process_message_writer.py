"""Serialized writes to a processing worker pipe."""

from __future__ import annotations

from threading import Lock
from typing import Any

from notekeeper.application.results import DashboardChangedEvent, ProgressEvent


class ProcessMessageWriter:
    def __init__(self, connection: Any) -> None:
        self._connection = connection
        self._lock = Lock()

    def publish(self, event: ProgressEvent | DashboardChangedEvent) -> None:
        kind = "progress" if isinstance(event, ProgressEvent) else "dashboard"
        self._send(kind, event)

    def result(self, value: Any) -> None:
        self._send("result", value)

    def error(self, value: str) -> None:
        self._send("error", value)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _send(self, kind: str, payload: Any) -> None:
        with self._lock:
            self._connection.send((kind, payload))


__all__ = ["ProcessMessageWriter"]
