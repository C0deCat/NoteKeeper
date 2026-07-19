"""Textual dashboard application composition."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from textual.app import App, ComposeResult
from textual.css.query import NoMatches
from textual.containers import Horizontal, ItemGrid, Vertical, VerticalScroll
from textual.worker import Worker, WorkerState
from textual.widgets import Button, DataTable, Footer, Header, Label, ProgressBar, Select, Static

from notekeeper.application import (
    ApplicationError,
    ClearFailedJobsForCampaignCommand,
    GetCampaignCommand,
    ListCampaignsCommand,
    ListJobsForCampaignCommand,
)
from notekeeper.domain import (
    AudioTrack,
    DomainError,
    JobStatus,
    Participant,
    ProcessingJob,
)

from ..contracts import InterfaceRuntime
from . import (
    campaign_app,
    diagnostics_app,
    job_app,
    participant_app,
    recap_app,
    recording_app,
    review_app,
    sample_app,
    transcript_app,
)
from .campaign_management_screen import ManageCampaignsScreen
from .clear_failed_jobs_screen import ClearFailedJobsScreen
from .common import format_duration, sync_result_status
from .identifier_data_table import IdentifierDataTable
from .participant_app import AddParticipantScreen


@dataclass(frozen=True, slots=True)
class DashboardWarning:
    """Selectable dashboard representation of a warning or job error row."""

    key: str
    job_id: str
    kind: str
    message: str


SelectedObject = ProcessingJob | AudioTrack | Participant | DashboardWarning


class NoteKeeperTui(App[None]):
    """Dashboard-first Textual interface for Stage 1."""

    CSS_PATH = Path(__file__).with_name("styles.tcss")

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("d", "diagnostics", "Diagnostics"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, runtime: InterfaceRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        self._selected_campaign_id: str | None = None
        self._selected_object: SelectedObject | None = None
        self._dashboard_jobs: dict[str, ProcessingJob] = {}
        self._dashboard_audio_tracks: dict[str, AudioTrack] = {}
        self._dashboard_participants: dict[str, Participant] = {}
        self._dashboard_warnings: dict[str, DashboardWarning] = {}
        self._participant_ids_with_samples: set[str] = set()
        self._campaign_has_participants = False
        self._campaign_is_processing_ready = False
        self._failed_job_count = 0
        self._clear_failed_jobs_in_progress = False
        self._job_delete_in_progress = False
        self._job_cancel_in_progress = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="topbar"):
            yield Select((), prompt="Campaign", id="campaign-select")
            yield Button("Manage Campaign", id="manage-campaign")
            yield Static("Ready", id="status")
        with ItemGrid(
            id="campaign-actions",
            min_column_width=20,
            stretch_height=False,
        ):
            yield Button("Refresh", id="refresh", variant="primary")
            yield Button("Sync Folder", id="sync-folder")
            yield Button("Add Player", id="add-player")
            yield Button("Add Voice Sample", id="add-sample")
            yield Button("Submit Recording", id="submit-recording")
            yield Button("Diagnostics", id="diagnostics")
        with Horizontal(id="dashboard"):
            with VerticalScroll(id="actions"):
                yield Button("Create Job", id="create-job")
                yield Button("Rename Recording", id="rename-recording")
                yield Button("Remove Recording", id="remove-recording", variant="error")
                yield Button("Rename Player", id="rename-player")
                yield Button("Remove Player", id="remove-player", variant="error")
                yield Button(
                    "Remove Voice Sample",
                    id="remove-voice-sample",
                    variant="error",
                )
                yield Button("Run", id="job-action", variant="success")
                yield Button("Delete", id="delete-job", variant="error")
                yield Button("Cancel", id="cancel-job", variant="warning")
                yield Button("Preview Transcript", id="preview-transcript")
                yield Button("Preview Recap", id="preview-recap")
                yield Button("Export Transcript", id="export-transcript")
                yield Button("Export Recap", id="export-recap")
                yield ProgressBar(total=None, id="job-progress")
            with Vertical(id="content"):
                with Horizontal(id="jobs-header"):
                    yield Label("Jobs")
                    yield Button(
                        "Clear Failed Jobs",
                        id="clear-failed-jobs",
                        variant="error",
                    )
                yield IdentifierDataTable(
                    id="jobs-table",
                    classes="panel short-panel",
                    show_cursor=False,
                )
                yield Label("Recordings")
                yield IdentifierDataTable(
                    id="recordings-table",
                    classes="panel short-panel",
                    show_cursor=False,
                )
                yield Label("Players")
                yield IdentifierDataTable(
                    id="players-table",
                    classes="panel short-panel",
                    show_cursor=False,
                )
                yield Label("Warnings and errors")
                yield IdentifierDataTable(
                    id="warnings-table",
                    classes="panel short-panel",
                    show_cursor=False,
                )
        yield Footer()

    def on_mount(self) -> None:
        self._progress().display = False
        self._setup_tables()
        self.refresh_dashboard()

    def action_refresh(self) -> None:
        self.refresh_dashboard()

    def action_diagnostics(self) -> None:
        self._open_diagnostics()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "campaign-select":
            return
        previous_campaign_id = self._selected_campaign_id
        if event.value in (Select.BLANK, Select.NULL):
            self._selected_campaign_id = None
        else:
            self._selected_campaign_id = str(event.value)
        if self._selected_campaign_id != previous_campaign_id:
            self._selected_object = None
        self.refresh_dashboard(update_campaigns=False)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not self._event_matches_table_cursor(event.data_table, event.row_key):
            return
        self._select_table_row(event.data_table, event.row_key, announce=True)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if not self._event_matches_table_cursor(event.data_table, event.row_key):
            return
        self._select_table_row(event.data_table, event.row_key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "refresh":
            self.refresh_dashboard()
        elif button_id == "manage-campaign":
            self._open_manage_campaigns()
        elif button_id == "sync-folder":
            self._with_campaign(self._sync_campaign_folder)
        elif button_id == "add-player":
            self._with_campaign(
                lambda campaign_id: self.push_screen(
                    AddParticipantScreen(),
                    lambda name: self._add_participant(campaign_id, name),
                ),
            )
        elif button_id == "add-sample":
            self._with_campaign(self._open_add_sample)
        elif button_id == "submit-recording":
            self._with_campaign(self._open_submit_recording)
        elif button_id == "create-job":
            self._create_job_for_selected_audio_track()
        elif button_id == "rename-recording":
            if isinstance(self._selected_object, AudioTrack):
                recording_app.open_rename_recording(self, self._selected_object)
        elif button_id == "remove-recording":
            if isinstance(self._selected_object, AudioTrack):
                recording_app.confirm_remove_recording(self, self._selected_object)
        elif button_id == "rename-player":
            if isinstance(self._selected_object, Participant):
                participant_app.open_rename_participant(self, self._selected_object)
        elif button_id == "remove-player":
            if isinstance(self._selected_object, Participant):
                participant_app.confirm_remove_participant(self, self._selected_object)
        elif button_id == "remove-voice-sample":
            if isinstance(self._selected_object, Participant):
                sample_app.open_remove_sample(self, self._selected_object)
        elif button_id == "job-action":
            self._perform_selected_job_action()
        elif button_id == "delete-job":
            job_app.confirm_delete_selected_job(self)
        elif button_id == "cancel-job":
            job_app.confirm_cancel_selected_job(self)
        elif button_id == "clear-failed-jobs":
            self._confirm_clear_failed_jobs()
        elif button_id == "preview-transcript":
            self._preview_transcript()
        elif button_id == "preview-recap":
            self._preview_recap()
        elif button_id == "export-transcript":
            self._export_transcript()
        elif button_id == "export-recap":
            self._export_recap()
        elif button_id == "diagnostics":
            self._open_diagnostics()

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.group not in {
            "cleanup", "job", "job-delete", "job-cancel", "review", "sync"
        }:
            return

        if event.state is WorkerState.RUNNING:
            self._progress().display = True
            if event.worker.group == "sync":
                self._set_status("Syncing")
            elif event.worker.group == "cleanup":
                self._set_status("Clearing failed jobs")
            elif event.worker.group == "job-delete":
                self._set_status("Deleting job")
            elif event.worker.group == "job-cancel":
                self._set_status("Canceling job")
            else:
                self._set_status("Running")
                if event.worker.group == "job":
                    self.set_timer(
                        0.1,
                        lambda: self.refresh_dashboard(update_campaigns=False),
                    )
        elif event.state is WorkerState.SUCCESS:
            self._progress().display = False
            if event.worker.group == "sync":
                message = sync_result_status(event.worker.result)
                self.refresh_dashboard(update_campaigns=False)
                self._set_status(message)
                self.notify(message)
            elif event.worker.group == "cleanup":
                self._clear_failed_jobs_in_progress = False
                deleted_count = len(event.worker.result.deleted_job_ids)
                self.refresh_dashboard(update_campaigns=False)
                message = f"Cleared {deleted_count} failed jobs"
                self._set_status(message)
                self.notify(message)
            elif event.worker.group == "job-delete":
                self._job_delete_in_progress = False
                self.refresh_dashboard(update_campaigns=False)
                message = f"Deleted job {event.worker.result.job_id}"
                self._set_status(message)
                self.notify(message)
            elif event.worker.group == "job-cancel":
                self._job_cancel_in_progress = False
                self.refresh_dashboard(update_campaigns=False)
                message = f"Canceled job {event.worker.result.job.id}"
                self._set_status(message)
                self.notify(message)
            else:
                self._set_status("Done")
                self.refresh_dashboard(update_campaigns=False)
        elif event.state is WorkerState.ERROR:
            self._progress().display = False
            if event.worker.group == "cleanup":
                self._clear_failed_jobs_in_progress = False
                self._update_action_buttons()
            elif event.worker.group == "job-delete":
                self._job_delete_in_progress = False
                self._update_action_buttons()
            elif event.worker.group == "job-cancel":
                self._job_cancel_in_progress = False
                self._update_action_buttons()
            message = str(event.worker.error) if event.worker.error else "worker failed"
            self._set_status(message)
            self.notify(message, severity="error")
        elif event.state is WorkerState.CANCELLED:
            self._progress().display = False
            if event.worker.group == "cleanup":
                self._clear_failed_jobs_in_progress = False
                self._update_action_buttons()
            elif event.worker.group == "job-delete":
                self._job_delete_in_progress = False
                self._update_action_buttons()
            elif event.worker.group == "job-cancel":
                self._job_cancel_in_progress = False
                self._update_action_buttons()

    def refresh_dashboard(self, *, update_campaigns: bool = True) -> None:
        try:
            if update_campaigns:
                self._refresh_campaign_select()
            self._refresh_campaign_panels()
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))

    def _setup_tables(self) -> None:
        self._reset_table("jobs-table", ("ID", "Status", "Transcript", "Recap", "Updated"))
        self._reset_table(
            "recordings-table",
            ("ID", "Title", "Duration", "Jobs", "Latest Status"),
        )
        self._reset_table("players-table", ("ID", "Name", "Voice Sample", "Ready"))
        self._reset_table("warnings-table", ("Job", "Kind", "Message"))

    def _refresh_campaign_select(self) -> None:
        campaigns = self.runtime.use_cases.list_campaigns.execute(
            ListCampaignsCommand(),
        ).campaigns
        options = tuple((campaign.name, str(campaign.id)) for campaign in campaigns)
        select = self.query_one("#campaign-select", Select)
        with select.prevent(Select.Changed):
            select.set_options(options)

            ids = {str(campaign.id) for campaign in campaigns}
            if not ids:
                self._selected_campaign_id = None
                self._selected_object = None
                select.clear()
                return

            if self._selected_campaign_id not in ids:
                self._selected_campaign_id = str(campaigns[0].id)
                self._selected_object = None
            select.value = self._selected_campaign_id

    def _refresh_campaign_panels(self) -> None:
        if self._selected_campaign_id is None:
            self._selected_object = None
            self._dashboard_jobs = {}
            self._dashboard_audio_tracks = {}
            self._dashboard_participants = {}
            self._dashboard_warnings = {}
            self._participant_ids_with_samples = set()
            self._campaign_has_participants = False
            self._campaign_is_processing_ready = False
            self._failed_job_count = 0
            self._clear_tables()
            self._set_status("No campaign")
            self._update_action_buttons()
            return

        campaign_id = self._selected_campaign_id
        campaign = self.runtime.use_cases.get_campaign.execute(
            GetCampaignCommand(campaign_id=campaign_id),
        ).campaign
        participants = campaign.participants
        voice_samples = campaign.voice_samples
        audio_tracks = campaign.audio_tracks
        jobs = self.runtime.use_cases.list_jobs_for_campaign.execute(
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
        sample_participants = {str(sample.participant_id) for sample in voice_samples}
        self._participant_ids_with_samples = sample_participants
        jobs_by_track: dict[str, list[ProcessingJob]] = {}
        for job in ordered_jobs:
            jobs_by_track.setdefault(str(job.audio_track_id), []).append(job)
        self._dashboard_jobs = {str(job.id): job for job in ordered_jobs}
        self._dashboard_audio_tracks = {
            str(audio_track.id): audio_track for audio_track in ordered_audio_tracks
        }
        self._dashboard_participants = {
            str(participant.id): participant for participant in ordered_participants
        }
        self._dashboard_warnings = {}
        self._campaign_has_participants = bool(participants)
        self._campaign_is_processing_ready = (
            self._campaign_has_participants
            and all(
                str(participant.id) in sample_participants
                for participant in participants
            )
        )
        self._failed_job_count = sum(
            job.status is JobStatus.FAILED for job in ordered_jobs
        )

        selected_key = self._selected_object_key(self._selected_object)

        jobs_table = self._reset_table(
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

        recordings_table = self._reset_table(
            "recordings-table",
            ("ID", "Title", "Duration", "Jobs", "Latest Status"),
        )
        for audio_track in ordered_audio_tracks:
            track_jobs = jobs_by_track.get(str(audio_track.id), [])
            latest_job = (
                max(track_jobs, key=lambda item: item.updated_at)
                if track_jobs
                else None
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

        players_table = self._reset_table(
            "players-table",
            ("ID", "Name", "Voice Sample", "Ready"),
        )
        for participant in ordered_participants:
            has_sample = str(participant.id) in sample_participants
            players_table.add_identifier_row(
                str(participant.id),
                participant.display_name,
                "yes" if has_sample else "no",
                "ready" if has_sample else "missing",
                identifier_indices=(0,),
                key=str(participant.id),
            )

        warnings_table = self._reset_table("warnings-table", ("Job", "Kind", "Message"))
        for job in ordered_jobs:
            duplicate_counts: dict[tuple[str, str], int] = {}
            for warning in job.warnings:
                signature = (warning.kind.value, warning.message)
                occurrence = duplicate_counts.get(signature, 0)
                duplicate_counts[signature] = occurrence + 1
                warning_key = (
                    f"{job.id}:warning:{warning.kind.value}:"
                    f"{warning.message}:{occurrence}"
                )
                dashboard_warning = DashboardWarning(
                    key=warning_key,
                    job_id=str(job.id),
                    kind=warning.kind.value,
                    message=warning.message,
                )
                self._dashboard_warnings[warning_key] = dashboard_warning
                warnings_table.add_identifier_row(
                    str(job.id),
                    warning.kind.value,
                    warning.message,
                    identifier_indices=(0,),
                    key=warning_key,
                )
            if job.error_message:
                error_key = f"{job.id}:error"
                self._dashboard_warnings[error_key] = DashboardWarning(
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

        self._selected_object = self._restore_selected_object(selected_key)
        if self._selected_object is None:
            self._selected_object = (
                ordered_jobs[0]
                if ordered_jobs
                else (ordered_audio_tracks[0] if ordered_audio_tracks else None)
            )
        self._sync_table_selection()
        self._set_status(f"{len(ordered_jobs)} jobs")
        self._update_action_buttons()

    def _clear_tables(self) -> None:
        self._setup_tables()

    def _reset_table(
        self,
        table_id: str,
        columns: Iterable[str],
    ) -> IdentifierDataTable:
        table = self.query_one(f"#{table_id}", IdentifierDataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        for column in columns:
            table.add_column(column)
        return table

    def _select_table_row(
        self,
        table: DataTable,
        row_id: object,
        *,
        announce: bool = False,
    ) -> None:
        selected_id = str(getattr(row_id, "value", row_id))
        previous_key = self._selected_object_key(self._selected_object)
        if table.id == "jobs-table":
            self._selected_object = self._dashboard_jobs.get(selected_id)
            selected_label = f"job {selected_id}"
        elif table.id == "recordings-table":
            self._selected_object = self._dashboard_audio_tracks.get(selected_id)
            selected_label = f"recording {selected_id}"
        elif table.id == "players-table":
            self._selected_object = self._dashboard_participants.get(selected_id)
            selected_label = f"player {selected_id}"
        elif table.id == "warnings-table":
            self._selected_object = self._dashboard_warnings.get(selected_id)
            selected_label = f"warning {selected_id}"
        else:
            return

        if self._selected_object_key(self._selected_object) == previous_key:
            if announce and self._selected_object is not None:
                self._set_status(f"Selected {selected_label}")
            return

        self._sync_table_selection()
        self._update_action_buttons()
        if announce and self._selected_object is not None:
            self._set_status(f"Selected {selected_label}")

    def _event_matches_table_cursor(
        self,
        table: DataTable,
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

    def _select_job_after_refresh(self, job_id: str) -> None:
        self._selected_object = self._dashboard_jobs.get(job_id)
        self._sync_table_selection()
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        """Enable only actions whose current dashboard context supports them."""
        campaign_selected = self._selected_campaign_id is not None
        selected_job = (
            self._selected_object
            if isinstance(self._selected_object, ProcessingJob)
            else None
        )
        selected_audio_track = (
            self._selected_object
            if isinstance(self._selected_object, AudioTrack)
            else None
        )
        selected_participant = (
            self._selected_object
            if isinstance(self._selected_object, Participant)
            else None
        )
        processing_ready = campaign_selected and self._campaign_is_processing_ready

        self._set_button_disabled("refresh", False)
        self._set_button_disabled("manage-campaign", False)
        self._set_button_disabled("diagnostics", False)
        self._set_button_disabled("sync-folder", not campaign_selected)
        self._set_button_disabled("add-player", not campaign_selected)
        self._set_button_disabled(
            "add-sample",
            not campaign_selected or not self._campaign_has_participants,
        )
        self._set_button_disabled("submit-recording", not processing_ready)
        self._set_button_disabled(
            "clear-failed-jobs",
            not campaign_selected
            or self._failed_job_count == 0
            or self._clear_failed_jobs_in_progress,
        )

        self._set_button_display("create-job", selected_audio_track is not None)
        self._set_button_disabled(
            "create-job",
            not processing_ready or selected_audio_track is None,
        )
        for button_id in ("rename-recording", "remove-recording"):
            self._set_button_display(button_id, selected_audio_track is not None)
            self._set_button_disabled(button_id, selected_audio_track is None)
        for button_id in (
            "rename-player",
            "remove-player",
            "remove-voice-sample",
        ):
            self._set_button_display(button_id, selected_participant is not None)
        self._set_button_disabled("rename-player", selected_participant is None)
        self._set_button_disabled("remove-player", selected_participant is None)
        self._set_button_disabled(
            "remove-voice-sample",
            selected_participant is None
            or str(selected_participant.id) not in self._participant_ids_with_samples,
        )
        for button_id in (
            "preview-transcript",
            "export-transcript",
            "preview-recap",
            "export-recap",
        ):
            self._set_button_display(button_id, selected_job is not None)
        action_labels = {
            JobStatus.PENDING: "Run",
            JobStatus.FAILED: "Restart",
            JobStatus.CANCELED: "Restart",
            JobStatus.WAITING_FOR_REVIEW: "Review and Continue",
        }
        action_label = (
            action_labels.get(selected_job.status)
            if selected_job is not None
            else None
        )
        self._set_button_display("job-action", action_label is not None)
        if action_label is not None:
            self.query_one("#job-action", Button).label = action_label
        self._set_button_disabled(
            "job-action",
            selected_job is None
            or action_label is None
            or (
                selected_job.status in {JobStatus.FAILED, JobStatus.CANCELED}
                and not processing_ready
            ),
        )
        for button_id in ("delete-job", "cancel-job"):
            self._set_button_display(button_id, selected_job is not None)
        self._set_button_disabled(
            "delete-job",
            selected_job is None
            or selected_job.status is JobStatus.RUNNING
            or self._job_delete_in_progress
            or self._job_cancel_in_progress,
        )
        self._set_button_disabled(
            "cancel-job",
            selected_job is None
            or selected_job.status is not JobStatus.RUNNING
            or self._job_cancel_in_progress
            or self._job_delete_in_progress,
        )
        self._set_button_disabled(
            "preview-transcript",
            selected_job is None or selected_job.transcript_id is None,
        )
        self._set_button_disabled(
            "export-transcript",
            selected_job is None or selected_job.transcript_id is None,
        )
        self._set_button_disabled(
            "preview-recap",
            selected_job is None or selected_job.recap_id is None,
        )
        self._set_button_disabled(
            "export-recap",
            selected_job is None or selected_job.recap_id is None,
        )

    def _set_button_disabled(self, button_id: str, disabled: bool) -> None:
        try:
            self.query_one(f"#{button_id}", Button).disabled = disabled
        except NoMatches:
            # Table events can finish dispatching while Textual tears down the screen.
            return

    def _set_button_display(self, button_id: str, display: bool) -> None:
        try:
            self.query_one(f"#{button_id}", Button).display = display
        except NoMatches:
            return

    def _selected_object_key(
        self,
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
        self,
        selected_key: tuple[str, str] | None,
    ) -> SelectedObject | None:
        if selected_key is None:
            return None
        object_type, object_id = selected_key
        objects = {
            "job": self._dashboard_jobs,
            "recording": self._dashboard_audio_tracks,
            "player": self._dashboard_participants,
            "warning": self._dashboard_warnings,
        }
        return objects.get(object_type, {}).get(object_id)

    def _sync_table_selection(self) -> None:
        selected_key = self._selected_object_key(self._selected_object)
        selected_table_id = {
            "job": "jobs-table",
            "recording": "recordings-table",
            "player": "players-table",
            "warning": "warnings-table",
        }.get(selected_key[0] if selected_key else "")

        tables = tuple(self.query(IdentifierDataTable))
        if not tables:
            return

        if selected_key is None or selected_table_id is None:
            for table in tables:
                if table.show_cursor:
                    table.show_cursor = False
            return
        try:
            table = self.query_one(f"#{selected_table_id}", IdentifierDataTable)
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

    def _open_manage_campaigns(self) -> None:
        self.push_screen(
            ManageCampaignsScreen(self.runtime, self._selected_campaign_id),
            self._finish_manage_campaigns,
        )

    def _finish_manage_campaigns(self, campaign_id: str | None) -> None:
        if campaign_id != self._selected_campaign_id:
            self._selected_object = None
        self._selected_campaign_id = campaign_id
        self.refresh_dashboard()

    def _add_participant(self, campaign_id: str, display_name: str | None) -> None:
        participant_app.add_participant(self, campaign_id, display_name)

    def _open_add_sample(self, campaign_id: str) -> None:
        sample_app.open_add_sample(self, campaign_id)

    def _open_submit_recording(self, campaign_id: str) -> None:
        recording_app.open_submit_recording(self, campaign_id)

    def _open_review(self, campaign_id: str) -> None:
        review_app.open_review(self, campaign_id)

    def _perform_selected_job_action(self) -> None:
        job = self._selected_job()
        if job is None:
            self._set_status("Select a job")
        elif job.status is JobStatus.PENDING:
            self._run_selected_job()
        elif job.status in {JobStatus.FAILED, JobStatus.CANCELED}:
            self._restart_selected_failed_job()
        elif job.status is JobStatus.WAITING_FOR_REVIEW:
            self._with_campaign(self._open_review)
        else:
            self._set_status("No action is available for this job")

    def _confirm_clear_failed_jobs(self) -> None:
        if self._selected_campaign_id is None:
            self._set_status("Select a campaign")
            return
        if self._failed_job_count == 0:
            self._set_status("No failed jobs to clear")
            return
        if self._clear_failed_jobs_in_progress:
            return
        self.push_screen(
            ClearFailedJobsScreen(self._failed_job_count),
            self._clear_failed_jobs,
        )

    def _clear_failed_jobs(self, confirmed: bool) -> None:
        campaign_id = self._selected_campaign_id
        if not confirmed or campaign_id is None:
            return
        self._clear_failed_jobs_in_progress = True
        self._update_action_buttons()
        self.run_worker(
            lambda: self.runtime.use_cases.clear_failed_jobs_for_campaign.execute(
                ClearFailedJobsForCampaignCommand(campaign_id=campaign_id),
            ),
            group="cleanup",
            thread=True,
            exit_on_error=False,
        )

    def _run_selected_job(self) -> None:
        job_app.run_selected_job(self)

    def _create_job_for_selected_audio_track(self) -> None:
        job_app.create_job_for_selected_audio_track(self)

    def _restart_selected_failed_job(self) -> None:
        job_app.restart_selected_failed_job(self)

    def _sync_campaign_folder(self, campaign_id: str) -> None:
        campaign_app.sync_campaign_folder(self, campaign_id)

    def _preview_transcript(self) -> None:
        transcript_app.preview_transcript(self)

    def _preview_recap(self) -> None:
        recap_app.preview_recap(self)

    def _export_transcript(self) -> None:
        transcript_app.export_transcript(self)

    def _export_recap(self) -> None:
        recap_app.export_recap(self)

    def _open_diagnostics(self) -> None:
        diagnostics_app.open_diagnostics(self)

    def _selected_job(self):
        if isinstance(self._selected_object, ProcessingJob):
            return self._selected_object
        return None

    def _with_campaign(self, action: Callable[[str], None]) -> None:
        if self._selected_campaign_id is None:
            self._set_status("Select a campaign")
            return
        action(self._selected_campaign_id)

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _progress(self) -> ProgressBar:
        return self.query_one("#job-progress", ProgressBar)


def run_tui(runtime: InterfaceRuntime) -> None:
    NoteKeeperTui(runtime).run()
