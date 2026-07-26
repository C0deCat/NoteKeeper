"""Rich-backed CLI progress rendering."""

from __future__ import annotations

from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
)

from notekeeper.application.results import ProgressEvent

from ..contracts import InterfaceRuntime


class CliProgressDisplay(AbstractContextManager["CliProgressDisplay"]):
    def __init__(self, runtime: InterfaceRuntime, operation_id: str) -> None:
        self._runtime = runtime
        self._operation_id = operation_id
        self._console = Console(stderr=True)
        self._progress: Progress | None = None
        self._task_id: Any = None
        self._last_stage: str | None = None
        self._unsubscribe = None

    def __enter__(self) -> "CliProgressDisplay":
        if self._console.is_terminal:
            self._progress = Progress(
                TextColumn("[bold][{task.fields[stage_counter]}]"),
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("{task.fields[timing]}"),
                console=self._console,
                transient=True,
            )
            self._progress.start()
            self._task_id = self._progress.add_task(
                "Preparing",
                total=100,
                stage_counter="0/0",
                timing="",
            )
        stream = getattr(self._runtime, "progress_events", None)
        if stream is not None:
            self._unsubscribe = stream.subscribe(
                self._operation_id,
                self._on_event,
            )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
        if self._progress is not None:
            self._progress.stop()
        return None

    def _on_event(self, event: ProgressEvent) -> None:
        stage = _stage_title(event.progress.stage)
        counter = f"{event.stage_index}/{event.stage_count}"
        if not self._console.is_terminal:
            if event.kind is ProgressEventKind.STARTED and stage != self._last_stage:
                self._console.print(f"[{counter}] {stage}")
                self._last_stage = stage
            return

        if self._progress is None or self._task_id is None:
            return
        self._progress.update(
            self._task_id,
            completed=event.progress.percent,
            description=stage,
            stage_counter=counter,
            timing=_timing_text(event),
            refresh=True,
        )


def _stage_title(stage: str) -> str:
    return stage.replace("_", " ").title()


def _timing_text(event: ProgressEvent) -> str:
    if event.timing_available:
        if event.progress.expected_duration == 0:
            return "estimating"
        current = _duration(event.progress.current_duration)
        expected = _duration(event.progress.expected_duration)
        remaining = _duration(event.progress.remaining_duration)
        return f"{current}/{expected}, remaining {remaining}"
    return ""


def _duration(milliseconds: int) -> str:
    seconds = milliseconds / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remainder = divmod(round(seconds), 60)
    return f"{minutes}m {remainder:02d}s"


__all__ = ["CliProgressDisplay"]
