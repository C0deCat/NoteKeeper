from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import Event

from notekeeper.application import ProgressEvent, ProgressEventKind
from notekeeper.domain import ProgressBar
from notekeeper.infrastructure.runtime import PersistedProgressEventHub
from notekeeper.infrastructure.sqlite import (
    SQLiteDatabase,
    SQLiteProgressEventSnapshotStore,
)


def test_persisted_hubs_exchange_active_and_terminal_progress(
    tmp_path: Path,
) -> None:
    owner, observer = _hubs(tmp_path)
    active = _event("job-1", current_duration=1)
    terminal = replace(active, kind=ProgressEventKind.COMPLETED)
    observed: list[ProgressEvent] = []
    changed = Event()

    owner.publish(active)
    unsubscribe = observer.subscribe(
        "job-1",
        lambda event: (observed.append(event), changed.set()),
    )
    assert observed == [active]
    assert observer.latest("job-1") == active

    changed.clear()
    owner.publish(terminal)
    assert changed.wait(1)
    assert observed[-1] == terminal
    assert observer.latest("job-1") is None
    unsubscribe()


def test_terminal_snapshot_is_not_replayed_but_new_execution_is_delivered(
    tmp_path: Path,
) -> None:
    owner, observer = _hubs(tmp_path)
    terminal = replace(
        _event("job-1", current_duration=5),
        kind=ProgressEventKind.COMPLETED,
    )
    owner.publish(terminal)
    observed: list[ProgressEvent] = []
    changed = Event()

    unsubscribe = observer.subscribe(
        "job-1",
        lambda event: (observed.append(event), changed.set()),
    )
    assert observed == []

    restarted = replace(
        terminal,
        kind=ProgressEventKind.STARTED,
        progress=ProgressBar(
            stage="mapping_speakers",
            expected_duration=0,
            current_duration=0,
        ),
    )
    owner.publish(restarted)
    assert changed.wait(1)
    assert observed == [restarted]
    unsubscribe()


def test_persisted_hub_keeps_operation_snapshots_independent(
    tmp_path: Path,
) -> None:
    owner, observer = _hubs(tmp_path)
    first = _event("job-a", current_duration=4)
    second = _event("job-b", current_duration=2)
    first_changed = Event()
    second_changed = Event()
    observed: dict[str, ProgressEvent] = {}

    unsubscribe_first = observer.subscribe(
        "job-a",
        lambda event: (observed.__setitem__(event.operation_id, event), first_changed.set()),
    )
    unsubscribe_second = observer.subscribe(
        "job-b",
        lambda event: (
            observed.__setitem__(event.operation_id, event),
            second_changed.set(),
        ),
    )
    owner.publish(first)
    owner.publish(second)

    assert first_changed.wait(1)
    assert second_changed.wait(1)
    assert observed == {"job-a": first, "job-b": second}
    assert observer.latest("job-a") == first
    assert observer.latest("job-b") == second
    unsubscribe_first()
    unsubscribe_second()


def _hubs(
    tmp_path: Path,
) -> tuple[PersistedProgressEventHub, PersistedProgressEventHub]:
    database = SQLiteDatabase(tmp_path / "notekeeper.sqlite3")
    database.initialize()
    return (
        PersistedProgressEventHub(
            SQLiteProgressEventSnapshotStore(database),
            poll_interval=0.01,
        ),
        PersistedProgressEventHub(
            SQLiteProgressEventSnapshotStore(database),
            poll_interval=0.01,
        ),
    )


def _event(operation_id: str, *, current_duration: int) -> ProgressEvent:
    return ProgressEvent(
        operation_id=operation_id,
        stage_index=4,
        stage_count=4,
        timing_available=True,
        kind=ProgressEventKind.UPDATED,
        progress=ProgressBar(
            stage="generating_recap",
            expected_duration=5,
            current_duration=current_duration,
        ),
    )
