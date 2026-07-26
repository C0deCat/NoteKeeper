"""Tests for runtime progress distribution and tracking."""

import logging

from notekeeper.application import ProgressEvent, ProgressEventKind
from notekeeper.domain import ProcessingStage, ProgressBar
from notekeeper.infrastructure.runtime import (
    InMemoryProgressEventHub,
    StreamingProgressTracker,
)
from notekeeper.infrastructure.runtime import progress_tracker as tracker_module


def _event(kind: ProgressEventKind = ProgressEventKind.UPDATED) -> ProgressEvent:
    return ProgressEvent(
        operation_id="job-1",
        stage_index=1,
        stage_count=2,
        timing_available=False,
        kind=kind,
        progress=ProgressBar("normalizing_audio", 1000, 500),
    )


def test_event_hub_replays_active_state_and_evicts_terminal_state() -> None:
    hub = InMemoryProgressEventHub()
    hub.publish(_event())
    received = []

    unsubscribe = hub.subscribe("job-1", received.append)
    hub.publish(_event(ProgressEventKind.COMPLETED))

    assert [event.kind for event in received] == [
        ProgressEventKind.UPDATED,
        ProgressEventKind.COMPLETED,
    ]
    assert hub.latest("job-1") is None

    unsubscribe()
    hub.publish(_event())
    assert len(received) == 2


def test_event_hub_isolates_failing_subscribers(caplog) -> None:
    hub = InMemoryProgressEventHub()
    received = []

    def fail(_event: ProgressEvent) -> None:
        raise RuntimeError("subscriber failed")

    hub.subscribe("job-1", fail)
    hub.subscribe("job-1", received.append)

    with caplog.at_level(logging.ERROR):
        hub.publish(_event())

    assert received == [_event()]
    assert "Progress subscriber failed" in caplog.text


def test_tracker_calculates_eta_and_throttles_updates(monkeypatch) -> None:
    now = [100.0]
    monkeypatch.setattr(tracker_module.time, "monotonic", lambda: now[0])
    events = []
    tracker = StreamingProgressTracker(
        _CollectingPublisher(events),
        "job-1",
        (ProcessingStage.TRANSCRIBING,),
    )
    try:
        tracker.start_stage(
            ProcessingStage.TRANSCRIBING,
            timing_available=True,
        )
        now[0] = 100.1
        tracker.update_fraction(0.25)
        assert len(events) == 1

        now[0] = 100.5
        tracker.update_fraction(0.5)
        update = events[-1]
        assert update.kind is ProgressEventKind.UPDATED
        assert update.progress.current_duration == 500
        assert update.progress.expected_duration == 1000
        assert update.progress.remaining_duration == 500

        tracker.complete_stage()
        tracker.complete()
        assert events[-1].kind is ProgressEventKind.COMPLETED
        assert events[-2].progress.percent == 100.0
    finally:
        tracker.close()


class _CollectingPublisher:
    def __init__(self, events: list[ProgressEvent]) -> None:
        self._events = events

    def publish(self, event: ProgressEvent) -> None:
        self._events.append(event)
