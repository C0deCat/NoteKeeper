"""Dashboard selection restoration and action-button state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.css.query import NoMatches
from textual.widgets import (
    Button,
)

from notekeeper.domain import (
    AudioTrack,
    JobStatus,
    Participant,
    ProcessingJob,
)

from .dashboard_messages import DashboardWarning, SelectedObject
from .identifier_data_table import IdentifierDataTable

if TYPE_CHECKING:
    from .tui import NoteKeeperTui


def _update_action_buttons(app: NoteKeeperTui) -> None:
    """Enable only actions whose current dashboard context supports them."""
    campaign_selected = app._selected_campaign_id is not None
    selected_job = (
        app._selected_object
        if isinstance(app._selected_object, ProcessingJob)
        else None
    )
    selected_audio_track = (
        app._selected_object if isinstance(app._selected_object, AudioTrack) else None
    )
    selected_participant = (
        app._selected_object if isinstance(app._selected_object, Participant) else None
    )
    processing_ready = campaign_selected and app._campaign_is_processing_ready
    campaign_mutable = campaign_selected and not app._campaign_has_active_jobs

    app._set_button_disabled("refresh", False)
    app._set_button_disabled(
        "manage-campaign",
        campaign_selected and app._campaign_has_active_jobs,
    )
    app._set_button_disabled(
        "settings",
        False if app._has_settings_service() else not campaign_mutable,
    )
    app._set_button_disabled("diagnostics", False)
    app._set_button_disabled("sync-folder", not campaign_mutable)
    app._set_button_disabled("add-player", not campaign_mutable)
    app._set_button_disabled(
        "add-sample",
        not campaign_mutable or not app._campaign_has_participants,
    )
    app._set_button_disabled(
        "submit-recording",
        not processing_ready or not campaign_mutable,
    )
    app._set_button_disabled(
        "clear-failed-jobs",
        not campaign_selected
        or app._failed_job_count == 0
        or app._clear_failed_jobs_in_progress,
    )

    app._set_button_display("create-job", selected_audio_track is not None)
    app._set_button_disabled(
        "create-job",
        not processing_ready or selected_audio_track is None,
    )
    for button_id in ("rename-recording", "remove-recording"):
        app._set_button_display(button_id, selected_audio_track is not None)
        app._set_button_disabled(
            button_id,
            selected_audio_track is None or not campaign_mutable,
        )
    for button_id in (
        "rename-player",
        "remove-player",
        "remove-voice-sample",
    ):
        app._set_button_display(button_id, selected_participant is not None)
    app._set_button_disabled(
        "rename-player",
        selected_participant is None or not campaign_mutable,
    )
    app._set_button_disabled(
        "remove-player",
        selected_participant is None or not campaign_mutable,
    )
    app._set_button_disabled(
        "remove-voice-sample",
        selected_participant is None
        or str(selected_participant.id) not in app._participant_ids_with_samples
        or not campaign_mutable,
    )
    for button_id in (
        "recreate-recap",
        "preview-transcript",
        "export-transcript",
        "preview-recap",
        "export-recap",
    ):
        app._set_button_display(button_id, selected_job is not None)
    action_labels = {
        JobStatus.PENDING: "Run",
        JobStatus.FAILED: "Restart",
        JobStatus.CANCELED: "Restart",
        JobStatus.WAITING_FOR_REVIEW: "Review and Continue",
    }
    action_label = (
        action_labels.get(selected_job.status) if selected_job is not None else None
    )
    app._set_button_display("job-action", action_label is not None)
    if action_label is not None:
        app.query_one("#job-action", Button).label = action_label
    app._set_button_disabled(
        "job-action",
        selected_job is None
        or action_label is None
        or (
            selected_job.status in {JobStatus.FAILED, JobStatus.CANCELED}
            and not processing_ready
        ),
    )
    for button_id in ("delete-job", "cancel-job"):
        app._set_button_display(button_id, selected_job is not None)
    app._set_button_disabled(
        "delete-job",
        selected_job is None
        or selected_job.status
        in {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.CANCELING}
        or app._job_delete_in_progress
        or app._job_cancel_in_progress,
    )
    app._set_button_disabled(
        "cancel-job",
        selected_job is None
        or selected_job.status
        not in {
            JobStatus.QUEUED,
            JobStatus.RUNNING,
            JobStatus.WAITING_FOR_REVIEW,
        }
        or str(selected_job.id) == app._review_job_id
        or app._job_cancel_in_progress
        or app._job_delete_in_progress,
    )
    app._set_button_disabled(
        "recreate-recap",
        selected_job is None
        or selected_job.transcript_id is None
        or app._recap_generation_in_progress,
    )
    app._set_button_disabled(
        "preview-transcript",
        selected_job is None or selected_job.transcript_id is None,
    )
    app._set_button_disabled(
        "export-transcript",
        selected_job is None or selected_job.transcript_id is None,
    )
    app._set_button_disabled(
        "preview-recap",
        selected_job is None or selected_job.recap_id is None,
    )
    app._set_button_disabled(
        "export-recap",
        selected_job is None or selected_job.recap_id is None,
    )


def _set_button_disabled(app: NoteKeeperTui, button_id: str, disabled: bool) -> None:
    try:
        app.query_one(f"#{button_id}", Button).disabled = disabled
    except NoMatches:
        # Table events can finish dispatching while Textual tears down the screen.
        return


def _set_button_display(app: NoteKeeperTui, button_id: str, display: bool) -> None:
    try:
        app.query_one(f"#{button_id}", Button).display = display
    except NoMatches:
        return


def _selected_object_key(
    app: NoteKeeperTui,
    selected_object: SelectedObject | None,
) -> tuple[str, str] | None:
    if isinstance(selected_object, ProcessingJob):
        return ("job", str(selected_object.id))
    if isinstance(selected_object, AudioTrack):
        return ("recording", str(selected_object.id))
    if isinstance(selected_object, Participant):
        return ("player", str(selected_object.id))
    if isinstance(selected_object, DashboardWarning):
        return ("warning", selected_object.key)
    return None


def _restore_selected_object(
    app: NoteKeeperTui,
    selected_key: tuple[str, str] | None,
) -> SelectedObject | None:
    if selected_key is None:
        return None
    object_type, object_id = selected_key
    objects = {
        "job": app._dashboard_jobs,
        "recording": app._dashboard_audio_tracks,
        "player": app._dashboard_participants,
        "warning": app._dashboard_warnings,
    }
    return objects.get(object_type, {}).get(object_id)


def _sync_table_selection(app: NoteKeeperTui) -> None:
    selected_key = app._selected_object_key(app._selected_object)
    selected_table_id = {
        "job": "jobs-table",
        "recording": "recordings-table",
        "player": "players-table",
        "warning": "warnings-table",
    }.get(selected_key[0] if selected_key else "")

    tables = tuple(app.query(IdentifierDataTable))
    if not tables:
        return

    if selected_key is None or selected_table_id is None:
        for table in tables:
            if table.show_cursor:
                table.show_cursor = False
        return
    try:
        table = app.query_one(f"#{selected_table_id}", IdentifierDataTable)
    except NoMatches:
        return
    try:
        selected_row = table.get_row_index(selected_key[1])
    except KeyError:
        return
    if table.cursor_row != selected_row:
        table.move_cursor(row=selected_row, scroll=False)

    for dashboard_table in tables:
        should_show_cursor = dashboard_table is table
        if dashboard_table.show_cursor != should_show_cursor:
            dashboard_table.show_cursor = should_show_cursor


__all__ = [
    "_restore_selected_object",
    "_selected_object_key",
    "_set_button_disabled",
    "_set_button_display",
    "_sync_table_selection",
    "_update_action_buttons",
]
