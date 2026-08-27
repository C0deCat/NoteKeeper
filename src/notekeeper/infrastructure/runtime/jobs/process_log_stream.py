"""Text stream that forwards complete worker output lines over a process pipe."""

from __future__ import annotations

from io import TextIOBase
from threading import RLock

from notekeeper.application import ConsoleLogSource

from .process_message_writer import ProcessMessageWriter


class ProcessLogStream(TextIOBase):
    def __init__(
        self,
        writer: ProcessMessageWriter,
        operation_id: str,
        source: ConsoleLogSource,
    ) -> None:
        super().__init__()
        self._writer = writer
        self._operation_id = operation_id
        self._source = source
        self._buffer = ""
        self._lock = RLock()

    @property
    def encoding(self) -> str:
        return "utf-8"

    @property
    def errors(self) -> str:
        return "replace"

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return False

    def write(self, value: str) -> int:
        if not isinstance(value, str):
            raise TypeError("worker console output must be text")
        if not value:
            return 0
        with self._lock:
            normalized = value.replace("\r\n", "\n").replace("\r", "\n")
            parts = (self._buffer + normalized).split("\n")
            self._buffer = parts.pop()
            for line in parts:
                if line:
                    self._writer.log(self._operation_id, self._source, line)
        return len(value)

    def flush(self) -> None:
        with self._lock:
            if self._buffer:
                self._writer.log(
                    self._operation_id,
                    self._source,
                    self._buffer,
                )
                self._buffer = ""


__all__ = ["ProcessLogStream"]
