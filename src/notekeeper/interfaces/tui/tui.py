"""Textual dashboard application composition."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.worker import Worker, WorkerState
from textual.widgets import Button, DataTable, Footer, Header, Label, ProgressBar, Select, Static

from notekeeper.application import (
    ApplicationError,
    ListAudioTracksCommand,
    ListCampaignsCommand,
    ListJobsForCampaignCommand,
    ListParticipantsCommand,
    ListVoiceSamplesCommand,
)
from notekeeper.domain import DomainError

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
from .campaign_app import CreateCampaignScreen
from .common import format_duration, sync_result_status
from .participant_app import AddParticipantScreen


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
        self._selected_job_id: str | None = None
        self._selected_audio_track_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="topbar"):
            yield Select((), prompt="Campaign", id="campaign-select")
            yield Static("Ready", id="status")
        with Horizontal(id="dashboard"):
            with VerticalScroll(id="actions"):
                yield Button("Refresh", id="refresh", variant="primary")
                yield Button("Sync Folder", id="sync-folder")
                yield Button("New Campaign", id="new-campaign")
                yield Button("Add Player", id="add-player")
                yield Button("Add Voice Sample", id="add-sample")
                yield Button("Submit Recording", id="submit-recording")
                yield Button("Create Job", id="create-job")
                yield Button("Run Job", id="run-job", variant="success")
                yield Button("Restart Failed Job", id="restart-job")
                yield Button("Review Mapping", id="review-job")
                yield Button("Preview Transcript", id="preview-transcript")
                yield Button("Preview Recap", id="preview-recap")
                yield Button("Export Transcript", id="export-transcript")
                yield Button("Export Recap", id="export-recap")
                yield Button("Diagnostics", id="diagnostics")
                yield ProgressBar(total=None, id="job-progress")
            with Vertical(id="content"):
                yield Label("Jobs")
                yield DataTable(id="jobs-table", classes="panel short-panel")
                yield Label("Recordings")
                yield DataTable(id="recordings-table", classes="panel short-panel")
                yield Label("Players")
                yield DataTable(id="players-table", classes="panel short-panel")
                yield Label("Warnings and errors")
                yield DataTable(id="warnings-table", classes="panel short-panel")
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
        if event.value in (Select.BLANK, Select.NULL):
            self._selected_campaign_id = None
        else:
            self._selected_campaign_id = str(event.value)
        self.refresh_dashboard(update_campaigns=False)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._select_table_row(event.data_table, event.row_key, announce=True)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._select_table_row(event.data_table, event.row_key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "refresh":
            self.refresh_dashboard()
        elif button_id == "sync-folder":
            self._with_campaign(self._sync_campaign_folder)
        elif button_id == "new-campaign":
            self.push_screen(CreateCampaignScreen(), self._create_campaign)
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
        elif button_id == "run-job":
            self._run_selected_job()
        elif button_id == "restart-job":
            self._restart_selected_failed_job()
        elif button_id == "review-job":
            self._with_campaign(self._open_review)
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
        if event.worker.group not in {"job", "review", "sync"}:
            return

        if event.state is WorkerState.RUNNING:
            self._progress().display = True
            self._set_status("Syncing" if event.worker.group == "sync" else "Running")
        elif event.state is WorkerState.SUCCESS:
            self._progress().display = False
            if event.worker.group == "sync":
                message = sync_result_status(event.worker.result)
                self.refresh_dashboard(update_campaigns=False)
                self._set_status(message)
                self.notify(message)
            else:
                self._set_status("Done")
                self.refresh_dashboard()
        elif event.state is WorkerState.ERROR:
            self._progress().display = False
            message = str(event.worker.error) if event.worker.error else "worker failed"
            self._set_status(message)
            self.notify(message, severity="error")

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
        select.set_options(options)

        ids = {str(campaign.id) for campaign in campaigns}
        if not ids:
            self._selected_campaign_id = None
            select.clear()
            return

        if self._selected_campaign_id not in ids:
            self._selected_campaign_id = str(campaigns[0].id)
        select.value = self._selected_campaign_id

    def _refresh_campaign_panels(self) -> None:
        if self._selected_campaign_id is None:
            self._clear_tables()
            self._set_status("No campaign")
            return

        campaign_id = self._selected_campaign_id
        participants = self.runtime.use_cases.list_participants.execute(
            ListParticipantsCommand(campaign_id=campaign_id),
        ).participants
        voice_samples = self.runtime.use_cases.list_voice_samples.execute(
            ListVoiceSamplesCommand(campaign_id=campaign_id),
        ).voice_samples
        audio_tracks = self.runtime.use_cases.list_audio_tracks.execute(
            ListAudioTracksCommand(campaign_id=campaign_id),
        ).audio_tracks
        jobs = self.runtime.use_cases.list_jobs_for_campaign.execute(
            ListJobsForCampaignCommand(campaign_id=campaign_id),
        ).jobs

        sample_participants = {str(sample.participant_id) for sample in voice_samples}
        jobs_by_track: dict[str, list] = {}
        for job in jobs:
            jobs_by_track.setdefault(str(job.audio_track_id), []).append(job)
        audio_track_ids = {str(audio_track.id) for audio_track in audio_tracks}
        self._selected_audio_track_id = (
            self._selected_audio_track_id
            if self._selected_audio_track_id in audio_track_ids
            else (str(audio_tracks[0].id) if audio_tracks else None)
        )
        self._selected_job_id = (
            self._selected_job_id
            if self._selected_job_id in {str(job.id) for job in jobs}
            else (str(jobs[-1].id) if jobs else None)
        )

        jobs_table = self._reset_table(
            "jobs-table",
            ("ID", "Status", "Transcript", "Recap", "Updated"),
        )
        for job in jobs:
            jobs_table.add_row(
                str(job.id),
                job.status.value,
                str(job.transcript_id or ""),
                str(job.recap_id or ""),
                job.updated_at.isoformat(timespec="seconds"),
                key=str(job.id),
            )

        recordings_table = self._reset_table(
            "recordings-table",
            ("ID", "Title", "Duration", "Jobs", "Latest Status"),
        )
        for audio_track in audio_tracks:
            track_jobs = jobs_by_track.get(str(audio_track.id), [])
            latest_job = max(track_jobs, key=lambda item: item.updated_at) if track_jobs else None
            recordings_table.add_row(
                str(audio_track.id),
                audio_track.title or audio_track.artifact.uri,
                format_duration(audio_track.metadata),
                str(len(track_jobs)),
                latest_job.status.value if latest_job is not None else "",
                key=str(audio_track.id),
            )

        players_table = self._reset_table(
            "players-table",
            ("ID", "Name", "Voice Sample", "Ready"),
        )
        for participant in participants:
            has_sample = str(participant.id) in sample_participants
            players_table.add_row(
                str(participant.id),
                participant.display_name,
                "yes" if has_sample else "no",
                "ready" if has_sample else "missing",
                key=str(participant.id),
            )

        warnings_table = self._reset_table("warnings-table", ("Job", "Kind", "Message"))
        for job in jobs:
            for warning in job.warnings:
                warnings_table.add_row(
                    str(job.id),
                    warning.kind.value,
                    warning.message,
                    key=f"{job.id}:{warning.kind.value}:{warning.message}",
                )
            if job.error_message:
                warnings_table.add_row(
                    str(job.id),
                    "error",
                    job.error_message,
                    key=f"{job.id}:error",
                )

        self._set_status(f"{len(jobs)} jobs")

    def _clear_tables(self) -> None:
        self._setup_tables()

    def _reset_table(self, table_id: str, columns: Iterable[str]) -> DataTable:
        table = self.query_one(f"#{table_id}", DataTable)
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
        if table.id == "jobs-table":
            self._selected_job_id = selected_id
            if announce:
                self._set_status(f"Selected job {self._selected_job_id}")
        elif table.id == "recordings-table":
            self._selected_audio_track_id = selected_id
            if announce:
                self._set_status(f"Selected recording {self._selected_audio_track_id}")

    def _select_job_after_refresh(self, job_id: str) -> None:
        self._selected_job_id = job_id
        jobs_table = self.query_one("#jobs-table", DataTable)
        try:
            jobs_table.move_cursor(row=jobs_table.get_row_index(job_id))
        except KeyError:
            pass

    def _create_campaign(self, name: str | None) -> None:
        campaign_app.create_campaign(self, name)

    def _add_participant(self, campaign_id: str, display_name: str | None) -> None:
        participant_app.add_participant(self, campaign_id, display_name)

    def _open_add_sample(self, campaign_id: str) -> None:
        sample_app.open_add_sample(self, campaign_id)

    def _open_submit_recording(self, campaign_id: str) -> None:
        recording_app.open_submit_recording(self, campaign_id)

    def _open_review(self, campaign_id: str) -> None:
        review_app.open_review(self, campaign_id)

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
        return job_app.selected_job(self)

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
