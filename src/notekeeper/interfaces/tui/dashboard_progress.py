"""Processing progress subscriptions and rendering."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from textual.containers import Vertical
from textual.widgets import (
    ProgressBar,
    Static,
)

from notekeeper.application import (
    ConsoleLogEvent,
    ConsoleLogSource,
    ProgressEvent,
    ProgressEventKind,
)
from notekeeper.domain import (
    JobStatus,
    ProcessingJob,
)

from .dashboard_messages import ProgressChanged

if TYPE_CHECKING:
    from .tui import NoteKeeperTui


_PROGRESS_JOB_STATUSES = {
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.CANCELING,
    JobStatus.WAITING_FOR_REVIEW,
}


def _progress_time_text(event: ProgressEvent) -> str:
    if not event.timing_available:
        return ""
    if event.progress.expected_duration == 0:
        return "Estimating…"
    current = _milliseconds(event.progress.current_duration)
    expected = _milliseconds(event.progress.expected_duration)
    remaining = _milliseconds(event.progress.remaining_duration)
    return f"{current} / {expected} · remaining {remaining}"


def _milliseconds(value: int) -> str:
    seconds = value / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remainder = divmod(round(seconds), 60)
    return f"{minutes}m {remainder:02d}s"


def _selected_job(app: NoteKeeperTui) -> ProcessingJob | None:
    if isinstance(app._selected_object, ProcessingJob):
        return app._selected_object
    return None


def _with_campaign(app: NoteKeeperTui, action: Callable[[str], object]) -> None:
    if app._selected_campaign_id is None:
        app._write_ui_log("Select a campaign")
        return
    action(app._selected_campaign_id)


def _write_ui_log(app: NoteKeeperTui, message: str) -> None:
    app._on_console_log_event(
        ConsoleLogEvent(None, ConsoleLogSource.LOGGING, message),
    )


def _set_job_count(app: NoteKeeperTui, count: int) -> None:
    app.query_one("#job-count", Static).update(f"{count} jobs")


def _progress(app: NoteKeeperTui) -> ProgressBar:
    return app.query_one("#job-progress", ProgressBar)


def _watch_progress(app: NoteKeeperTui, operation_id: str) -> None:
    if operation_id in app._progress_unsubscribes:
        return
    stream = app.runtime.progress_events
    app._progress_unsubscribes[operation_id] = stream.subscribe(
        operation_id,
        app._on_progress_event,
    )


def _on_progress_event(app: NoteKeeperTui, event: ProgressEvent) -> None:
    app.post_message(ProgressChanged(event))


def on_progress_changed(app: NoteKeeperTui, message: ProgressChanged) -> None:
    event = message.event
    if event.kind is ProgressEventKind.STARTED:
        app._set_console_expanded(True)
    app._apply_progress_event(event)
    if (
        event.kind.is_terminal
        and event.kind is not ProgressEventKind.PAUSED
        and app._recap_generation_in_progress
        and app._selected_job_id() == event.operation_id
    ):
        app._recap_generation_in_progress = False
        app._update_action_buttons()
    dashboard_job = app._dashboard_jobs.get(event.operation_id)
    if dashboard_job is not None and (
        event.kind is ProgressEventKind.STARTED
        or event.kind.is_terminal
        or dashboard_job.status in {JobStatus.QUEUED, JobStatus.WAITING_FOR_REVIEW}
    ):
        app._pending_content_refresh = True
        app._schedule_dashboard_refresh()


def _apply_progress_event(app: NoteKeeperTui, event: ProgressEvent) -> None:
    if event.kind.is_terminal:
        app._active_progress_events.pop(event.operation_id, None)
        if event.kind is not ProgressEventKind.PAUSED:
            unsubscribe = app._progress_unsubscribes.pop(
                event.operation_id,
                None,
            )
            if unsubscribe is not None:
                unsubscribe()
        if app._selected_job_id() == event.operation_id:
            app._hide_progress()
        return

    app._active_progress_events[event.operation_id] = event
    if app._selected_job_id() != event.operation_id:
        return
    app.query_one("#progress-panel", Vertical).display = True
    stage = event.progress.stage.replace("_", " ").title()
    app.query_one("#progress-stage", Static).update(
        f"[{event.stage_index}/{event.stage_count}] {stage}",
    )
    app._progress().update(total=100, progress=event.progress.percent)
    app.query_one("#progress-time", Static).update(
        _progress_time_text(event),
    )


def _show_selected_progress(app: NoteKeeperTui) -> None:
    operation_id = app._selected_job_id()
    if operation_id is None:
        app._hide_progress()
        return
    event = app._active_progress_events.get(operation_id)
    if event is None:
        event = app.runtime.progress_events.latest(operation_id)
    if event is None:
        app._hide_progress()
        return
    app._apply_progress_event(event)


def _sync_progress_subscriptions(
    app: NoteKeeperTui,
    jobs: tuple[ProcessingJob, ...],
) -> None:
    tracked_ids = {str(job.id) for job in jobs if job.status in _PROGRESS_JOB_STATUSES}
    selected_job = app._selected_job()
    if app._recap_generation_in_progress and selected_job is not None:
        tracked_ids.add(str(selected_job.id))

    for operation_id in tracked_ids:
        app._watch_progress(operation_id)

    for operation_id in tuple(app._progress_unsubscribes):
        if operation_id in tracked_ids:
            continue
        unsubscribe = app._progress_unsubscribes.pop(operation_id)
        unsubscribe()
        app._active_progress_events.pop(operation_id, None)


def _selected_job_id(app: NoteKeeperTui) -> str | None:
    job = app._selected_job()
    return str(job.id) if job is not None else None


def _hide_progress(app: NoteKeeperTui) -> None:
    app.query_one("#progress-panel", Vertical).display = False


def _hide_progress_if_inactive(app: NoteKeeperTui) -> None:
    operation_id = app._selected_job_id()
    if operation_id not in app._active_progress_events:
        app._hide_progress()


def on_unmount(app: NoteKeeperTui) -> None:
    if app._dashboard_unsubscribe is not None:
        app._dashboard_unsubscribe()
        app._dashboard_unsubscribe = None
    for unsubscribe in tuple(app._progress_unsubscribes.values()):
        unsubscribe()
    app._progress_unsubscribes.clear()
    app.runtime.shutdown_job_manager()


__all__ = [
    "_apply_progress_event",
    "_hide_progress",
    "_hide_progress_if_inactive",
    "_on_progress_event",
    "_progress",
    "_selected_job",
    "_selected_job_id",
    "_set_job_count",
    "_show_selected_progress",
    "_sync_progress_subscriptions",
    "_watch_progress",
    "_write_ui_log",
    "_with_campaign",
    "on_progress_changed",
    "on_unmount",
]
