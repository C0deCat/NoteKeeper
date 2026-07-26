"""Streaming progress tracker implementation."""

from __future__ import annotations

import math
import time
from threading import Event, RLock, Thread, current_thread

from notekeeper.application.ports import ProgressEventPublisher
from notekeeper.application.results import ProgressEvent, ProgressEventKind
from notekeeper.domain import ProcessingStage, ProgressBar


class StreamingProgressTracker:
    """Tracks one operation and publishes immutable snapshots."""

    def __init__(
        self,
        publisher: ProgressEventPublisher,
        operation_id: str,
        stages: tuple[ProcessingStage, ...],
        *,
        heartbeat_interval: float = 0.25,
    ) -> None:
        if not operation_id.strip():
            raise ValueError("operation_id must not be empty")
        if not stages:
            raise ValueError("stages must not be empty")
        if heartbeat_interval < 0.25:
            raise ValueError("heartbeat_interval must be at least 0.25 seconds")
        self._publisher = publisher
        self._operation_id = operation_id
        self._stages = stages
        self._heartbeat_interval = heartbeat_interval
        self._lock = RLock()
        self._stop = Event()
        self._stage_index = -1
        self._bar = ProgressBar(stage=stages[0].value)
        self._timing_available = False
        self._fraction = 0.0
        self._stage_completed = False
        self._stage_started_at = time.monotonic()
        self._last_update_published_at = 0.0
        self._terminal = False
        self._thread = Thread(
            target=self._heartbeat,
            name=f"progress-{operation_id}",
            daemon=True,
        )
        self._thread.start()

    def start_stage(
        self,
        stage: ProcessingStage,
        *,
        timing_available: bool,
    ) -> None:
        with self._lock:
            expected_index = self._stage_index + 1
            if expected_index >= len(self._stages):
                raise RuntimeError("all progress stages have already started")
            if self._stages[expected_index] is not stage:
                raise ValueError(
                    f"expected stage {self._stages[expected_index].value}, "
                    f"got {stage.value}"
                )
            self._stage_index = expected_index
            self._bar = self._bar.update_stage(stage.value)
            self._timing_available = timing_available
            self._fraction = 0.0
            self._stage_completed = False
            self._stage_started_at = time.monotonic()
            self._last_update_published_at = self._stage_started_at
            event = self._event(ProgressEventKind.STARTED)
        self._publisher.publish(event)

    def update_fraction(self, fraction: float) -> None:
        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
            raise ValueError("fraction must be a number")
        if not math.isfinite(fraction):
            raise ValueError("fraction must be finite")
        normalized = min(max(float(fraction), 0.0), 1.0)
        with self._lock:
            self._require_active_stage()
            if self._stage_completed:
                raise RuntimeError("progress stage has already completed")
            self._fraction = normalized
            self._refresh_bar()
            now = time.monotonic()
            if (
                normalized < 1.0
                and now - self._last_update_published_at
                < self._heartbeat_interval
            ):
                return
            self._last_update_published_at = now
            event = self._event(ProgressEventKind.UPDATED)
        self._publisher.publish(event)

    def complete_stage(self) -> None:
        with self._lock:
            self._require_active_stage()
            self._fraction = 1.0
            self._refresh_bar()
            self._stage_completed = True
            event = self._event(ProgressEventKind.STAGE_COMPLETED)
        self._publisher.publish(event)

    def complete(self) -> None:
        self._terminal_event(ProgressEventKind.COMPLETED)

    def pause(self) -> None:
        self._terminal_event(ProgressEventKind.PAUSED)

    def fail(self) -> None:
        self._terminal_event(ProgressEventKind.FAILED)

    def cancel(self) -> None:
        self._terminal_event(ProgressEventKind.CANCELED)

    def close(self) -> None:
        self._stop.set()
        if self._thread is not current_thread():
            self._thread.join(timeout=self._heartbeat_interval * 2)

    def _terminal_event(self, kind: ProgressEventKind) -> None:
        with self._lock:
            if self._terminal:
                return
            if self._stage_index < 0:
                self._stage_index = 0
                self._bar = self._bar.update_stage(self._stages[0].value)
                self._timing_available = False
                self._fraction = 0.0
            self._terminal = True
            event = self._event(kind)
        self._publisher.publish(event)
        self._stop.set()

    def _heartbeat(self) -> None:
        while not self._stop.wait(self._heartbeat_interval):
            with self._lock:
                if (
                    self._stage_index < 0
                    or self._stage_completed
                    or self._terminal
                ):
                    continue
                if not self._timing_available or self._fraction <= 0.0:
                    continue
                self._refresh_bar()
                self._last_update_published_at = time.monotonic()
                event = self._event(ProgressEventKind.UPDATED)
            self._publisher.publish(event)

    def _refresh_bar(self) -> None:
        if not self._timing_available:
            self._bar = (
                self._bar.update_expected_duration(1000)
                .update_current_duration(round(1000 * self._fraction))
            )
            return
        if self._fraction <= 0.0:
            self._bar = (
                self._bar.update_expected_duration(0)
                .update_current_duration(0)
            )
            return
        elapsed = max(round((time.monotonic() - self._stage_started_at) * 1000), 1)
        expected = max(elapsed, round(elapsed / self._fraction))
        self._bar = (
            self._bar.update_expected_duration(expected)
            .update_current_duration(elapsed)
        )

    def _event(self, kind: ProgressEventKind) -> ProgressEvent:
        return ProgressEvent(
            operation_id=self._operation_id,
            stage_index=self._stage_index + 1,
            stage_count=len(self._stages),
            timing_available=self._timing_available,
            kind=kind,
            progress=self._bar,
        )

    def _require_active_stage(self) -> None:
        if self._stage_index < 0:
            raise RuntimeError("progress stage has not started")


__all__ = ["StreamingProgressTracker"]
