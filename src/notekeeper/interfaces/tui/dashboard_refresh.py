"""Dashboard data loading and table refresh operations."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from textual import events
from textual.widgets import (
    DataTable,
    Select,
)

from notekeeper.application import (
    ApplicationError,
    DashboardChangedEvent,
    DashboardRefreshScope,
    GetCampaignCommand,
    ListCampaignsCommand,
    ListJobsForCampaignCommand,
)
from notekeeper.domain import (
    DomainError,
    JobStatus,
    ProcessingJob,
)

from .common import format_duration
from .dashboard_messages import (
    DashboardInvalidated,
    DashboardWarning,
)
from .identifier_data_table import IdentifierDataTable

if TYPE_CHECKING:
    from .tui import NoteKeeperTui


def refresh_dashboard(
    app: NoteKeeperTui,
    *,
    update_campaigns: bool = True,
    announce: bool = True,
) -> None:
    try:
        if update_campaigns:
            app._refresh_campaign_select()
        app._refresh_campaign_panels(announce=announce)
    except (ApplicationError, DomainError, ValueError) as exc:
        app._write_ui_log(str(exc))


def _setup_tables(app: NoteKeeperTui) -> None:
    app._reset_table("jobs-table", ("ID", "Status", "Transcript", "Recap", "Updated"))
    app._reset_table(
        "recordings-table",
        ("ID", "Title", "Duration", "Jobs", "Latest Status"),
    )
    app._reset_table("players-table", ("ID", "Name", "Voice Samples", "Ready"))
    app._reset_table("warnings-table", ("Job", "Kind", "Message"))


def _refresh_campaign_select(app: NoteKeeperTui) -> None:
    campaigns = app.runtime.use_cases.campaigns.list.execute(
        ListCampaignsCommand(),
    ).campaigns
    options = tuple((campaign.name, str(campaign.id)) for campaign in campaigns)
    select = app.query_one("#campaign-select", Select)
    with select.prevent(Select.Changed):
        select.set_options(options)

        ids = {str(campaign.id) for campaign in campaigns}
        if not ids:
            app._selected_campaign_id = None
            app._selected_object = None
            select.clear()
            return

        if app._selected_campaign_id not in ids:
            app._selected_campaign_id = str(campaigns[0].id)
            app._selected_object = None
        select.value = app._selected_campaign_id


def _refresh_campaign_panels(app: NoteKeeperTui, *, announce: bool = True) -> None:
    if app._selected_campaign_id is None:
        app._selected_object = None
        app._dashboard_jobs = {}
        app._dashboard_audio_tracks = {}
        app._dashboard_participants = {}
        app._dashboard_warnings = {}
        app._participant_ids_with_samples = set()
        app._campaign_has_participants = False
        app._campaign_is_processing_ready = False
        app._failed_job_count = 0
        app._campaign_has_active_jobs = False
        app._clear_tables()
        app._sync_progress_subscriptions(())
        app._hide_progress()
        app._set_job_count(0)
        if announce:
            app._write_ui_log("No campaign")
        app._update_action_buttons()
        return

    campaign_id = app._selected_campaign_id
    campaign = app.runtime.use_cases.campaigns.get.execute(
        GetCampaignCommand(campaign_id=campaign_id),
    ).campaign
    participants = campaign.participants
    voice_samples = campaign.voice_samples
    audio_tracks = campaign.audio_tracks
    jobs = app.runtime.use_cases.jobs.list_for_campaign.execute(
        ListJobsForCampaignCommand(campaign_id=campaign_id),
    ).jobs

    ordered_jobs = tuple(
        job
        for _, job in sorted(
            enumerate(jobs),
            key=lambda item: (
                item[1].updated_at,
                item[1].created_at,
                item[0],
            ),
            reverse=True,
        )
    )
    ordered_audio_tracks = tuple(reversed(audio_tracks))
    ordered_participants = tuple(reversed(participants))
    sample_counts: dict[str, int] = {}
    for sample in voice_samples:
        participant_id = str(sample.participant_id)
        sample_counts[participant_id] = sample_counts.get(participant_id, 0) + 1
    sample_participants = set(sample_counts)
    app._participant_ids_with_samples = sample_participants
    jobs_by_track: dict[str, list[ProcessingJob]] = {}
    for job in ordered_jobs:
        jobs_by_track.setdefault(str(job.audio_track_id), []).append(job)
    app._dashboard_jobs = {str(job.id): job for job in ordered_jobs}
    app._dashboard_audio_tracks = {
        str(audio_track.id): audio_track for audio_track in ordered_audio_tracks
    }
    app._dashboard_participants = {
        str(participant.id): participant for participant in ordered_participants
    }
    app._dashboard_warnings = {}
    app._campaign_has_participants = bool(participants)
    app._campaign_is_processing_ready = app._campaign_has_participants and all(
        str(participant.id) in sample_participants for participant in participants
    )
    app._failed_job_count = sum(job.status is JobStatus.FAILED for job in ordered_jobs)
    app._campaign_has_active_jobs = any(
        job.status
        in {
            JobStatus.QUEUED,
            JobStatus.RUNNING,
            JobStatus.CANCELING,
            JobStatus.WAITING_FOR_REVIEW,
        }
        for job in ordered_jobs
    )

    selected_key = app._selected_object_key(app._selected_object)

    jobs_table = app._reset_table(
        "jobs-table",
        ("ID", "Status", "Transcript", "Recap", "Updated"),
    )
    for job in ordered_jobs:
        jobs_table.add_identifier_row(
            str(job.id),
            job.status.value,
            str(job.transcript_id or ""),
            str(job.recap_id or ""),
            job.updated_at.isoformat(timespec="seconds"),
            identifier_indices=(0, 2, 3),
            key=str(job.id),
        )

    recordings_table = app._reset_table(
        "recordings-table",
        ("ID", "Title", "Duration", "Jobs", "Latest Status"),
    )
    for audio_track in ordered_audio_tracks:
        track_jobs = jobs_by_track.get(str(audio_track.id), [])
        latest_job = (
            max(track_jobs, key=lambda item: item.updated_at) if track_jobs else None
        )
        recordings_table.add_identifier_row(
            str(audio_track.id),
            audio_track.title or audio_track.artifact.uri,
            format_duration(audio_track.metadata),
            str(len(track_jobs)),
            latest_job.status.value if latest_job is not None else "",
            identifier_indices=(0,),
            key=str(audio_track.id),
        )

    players_table = app._reset_table(
        "players-table",
        ("ID", "Name", "Voice Samples", "Ready"),
    )
    for participant in ordered_participants:
        sample_count = sample_counts.get(str(participant.id), 0)
        has_sample = sample_count > 0
        players_table.add_identifier_row(
            str(participant.id),
            participant.display_name,
            str(sample_count),
            "ready" if has_sample else "missing",
            identifier_indices=(0,),
            key=str(participant.id),
        )

    warnings_table = app._reset_table("warnings-table", ("Job", "Kind", "Message"))
    for job in ordered_jobs:
        duplicate_counts: dict[tuple[str, str], int] = {}
        for warning in job.warnings:
            signature = (warning.kind.value, warning.message)
            occurrence = duplicate_counts.get(signature, 0)
            duplicate_counts[signature] = occurrence + 1
            warning_key = (
                f"{job.id}:warning:{warning.kind.value}:{warning.message}:{occurrence}"
            )
            dashboard_warning = DashboardWarning(
                key=warning_key,
                job_id=str(job.id),
                kind=warning.kind.value,
                message=warning.message,
            )
            app._dashboard_warnings[warning_key] = dashboard_warning
            warnings_table.add_identifier_row(
                str(job.id),
                warning.kind.value,
                warning.message,
                identifier_indices=(0,),
                key=warning_key,
            )
        if job.error_message:
            error_key = f"{job.id}:error"
            app._dashboard_warnings[error_key] = DashboardWarning(
                key=error_key,
                job_id=str(job.id),
                kind="error",
                message=job.error_message,
            )
            warnings_table.add_identifier_row(
                str(job.id),
                "error",
                job.error_message,
                identifier_indices=(0,),
                key=error_key,
            )

    app._selected_object = app._restore_selected_object(selected_key)
    if app._selected_object is None:
        app._selected_object = (
            ordered_jobs[0]
            if ordered_jobs
            else (ordered_audio_tracks[0] if ordered_audio_tracks else None)
        )
    app._sync_table_selection()
    app._set_job_count(len(ordered_jobs))
    app._update_action_buttons()
    app._sync_progress_subscriptions(ordered_jobs)
    app._show_selected_progress()


def _on_dashboard_changed(app: NoteKeeperTui, event: DashboardChangedEvent) -> None:
    app.post_message(DashboardInvalidated(event))


def on_dashboard_invalidated(app: NoteKeeperTui, message: DashboardInvalidated) -> None:
    event = message.event
    if event.scope is DashboardRefreshScope.CAMPAIGN_LIST:
        app._pending_full_refresh = True
    elif event.campaign_id == app._selected_campaign_id:
        app._pending_content_refresh = True
    else:
        return
    if len(app.screen_stack) > 1:
        return
    app._schedule_dashboard_refresh()


def on_screen_resume(app: NoteKeeperTui, event: events.ScreenResume) -> None:
    if app._pending_full_refresh or app._pending_content_refresh:
        app._schedule_dashboard_refresh()


def _schedule_dashboard_refresh(app: NoteKeeperTui) -> None:
    if app._dashboard_refresh_scheduled:
        return
    app._dashboard_refresh_scheduled = True
    app.call_later(app._flush_dashboard_refresh)


def _flush_dashboard_refresh(app: NoteKeeperTui) -> None:
    update_campaigns = app._pending_full_refresh
    update_content = update_campaigns or app._pending_content_refresh
    app._dashboard_refresh_scheduled = False
    app._pending_full_refresh = False
    app._pending_content_refresh = False
    if not update_content:
        return
    app.refresh_dashboard(
        update_campaigns=update_campaigns,
        announce=False,
    )
    pending_job_id = app._pending_selected_job_id
    if pending_job_id is not None and pending_job_id in app._dashboard_jobs:
        app._pending_selected_job_id = None
        app._select_job_after_refresh(pending_job_id)


def _clear_tables(app: NoteKeeperTui) -> None:
    app._setup_tables()


def _reset_table(
    app: NoteKeeperTui,
    table_id: str,
    columns: Iterable[str],
) -> IdentifierDataTable:
    table = app.query_one(f"#{table_id}", IdentifierDataTable)
    table.clear(columns=True)
    table.cursor_type = "row"
    for column in columns:
        table.add_column(column)
    return table


def _select_table_row(
    app: NoteKeeperTui,
    table: DataTable[object],
    row_id: object,
    *,
    announce: bool = False,
) -> None:
    selected_id = str(getattr(row_id, "value", row_id))
    previous_key = app._selected_object_key(app._selected_object)
    if table.id == "jobs-table":
        app._selected_object = app._dashboard_jobs.get(selected_id)
        selected_label = f"job {selected_id}"
    elif table.id == "recordings-table":
        app._selected_object = app._dashboard_audio_tracks.get(selected_id)
        selected_label = f"recording {selected_id}"
    elif table.id == "players-table":
        app._selected_object = app._dashboard_participants.get(selected_id)
        selected_label = f"player {selected_id}"
    elif table.id == "warnings-table":
        app._selected_object = app._dashboard_warnings.get(selected_id)
        selected_label = f"warning {selected_id}"
    else:
        return

    if app._selected_object_key(app._selected_object) == previous_key:
        if announce and app._selected_object is not None:
            app._write_ui_log(f"Selected {selected_label}")
        return

    app._sync_table_selection()
    app._update_action_buttons()
    app._show_selected_progress()
    if announce and app._selected_object is not None:
        app._write_ui_log(f"Selected {selected_label}")


def _event_matches_table_cursor(
    app: NoteKeeperTui,
    table: DataTable[object],
    row_key: object,
) -> bool:
    if not table.show_cursor:
        return False
    try:
        current_row_key = table.ordered_rows[table.cursor_row].key
    except IndexError:
        return False
    return str(getattr(row_key, "value", row_key)) == str(
        getattr(current_row_key, "value", current_row_key),
    )


def _select_job_after_refresh(app: NoteKeeperTui, job_id: str) -> None:
    app._selected_object = app._dashboard_jobs.get(job_id)
    app._sync_table_selection()
    app._update_action_buttons()
    app._show_selected_progress()


__all__ = [
    "_clear_tables",
    "_event_matches_table_cursor",
    "_flush_dashboard_refresh",
    "_on_dashboard_changed",
    "_refresh_campaign_panels",
    "_refresh_campaign_select",
    "_reset_table",
    "_schedule_dashboard_refresh",
    "_select_job_after_refresh",
    "_select_table_row",
    "_setup_tables",
    "on_dashboard_invalidated",
    "on_screen_resume",
    "refresh_dashboard",
]
