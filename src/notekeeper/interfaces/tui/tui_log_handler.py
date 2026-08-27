"""Logging handler that forwards parent-process records to the Textual app."""

from __future__ import annotations

import logging
from collections.abc import Callable

from notekeeper.application import ConsoleLogEvent, ConsoleLogSource


class TuiLogHandler(logging.Handler):
    def __init__(self, listener: Callable[[ConsoleLogEvent], None]) -> None:
        super().__init__()
        self._listener = listener
        self.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            return
        if message:
            self._listener(
                ConsoleLogEvent(None, ConsoleLogSource.LOGGING, message),
            )


__all__ = ["TuiLogHandler"]
