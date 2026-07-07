"""Textual dashboard adapter."""

from __future__ import annotations

from collections.abc import Iterable

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.worker import Worker, WorkerState
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    ProgressBar,
    Select,
    Static,
    TextArea,
)

from notekeeper.application import (
    AddParticipantToCampaignCommand,
    AddVoiceSampleCommand,
    ApplicationError,
    CreateCampaignCommand,
    CreateProcessingJobForAudioTrackCommand,
    ExportRecapMarkdownCommand,
    ExportTranscriptMarkdownCommand,
    GetJobStatusCommand,
    InspectAudioMetadataCommand,
    ListAudioTracksCommand,
    ListCampaignsCommand,
    ListJobsForCampaignCommand,
    ListParticipantsCommand,
    ListVoiceSamplesCommand,
    ManualSpeakerMappingCommand,
    PreviewRecapMarkdownCommand,
    PreviewTranscriptMarkdownCommand,
    ReviewSpeakerMappingsCommand,
    RunProcessingJobCommand,
    SubmitRecordingForProcessingCommand,
    SyncCampaignFolderCommand,
)
from notekeeper.domain import AudioMetadata, DomainError, JobStatus

from .contracts import InterfaceRuntime, RuntimeDiagnostics


class NoteKeeperTui(App[None]):
    """Dashboard-first Textual interface for Stage 1."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #topbar {
        height: 3;
        padding: 0 1;
        background: $panel;
    }

    #campaign-select {
        width: 1fr;
    }

    #status {
        width: 38;
        content-align: right middle;
    }

    #dashboard {
        height: 1fr;
        overflow-y: auto;
    }

    #actions {
        width: 28;
        height: 1fr;
        padding: 1;
        background: $surface;
        overflow-y: auto;
    }

    #actions Button {
        width: 100%;
        margin-bottom: 1;
    }

    #content {
        width: 1fr;
        padding: 1;
        overflow-y: auto;
        overflow-x: auto;
    }

    .panel {
        height: 1fr;
        border: solid $accent;
        padding: 1;
        margin-bottom: 1;
    }

    .short-panel {
        height: 12;
    }

    .modal {
        width: 72;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: thick $accent;
        background: $panel;
    }

    .modal Button {
        margin-right: 1;
    }

    .metadata {
        min-height: 5;
        border: solid $secondary;
        padding: 1;
        margin: 1 0;
    }

    #preview-markdown {
        height: 28;
        border: solid $accent;
        padding: 1;
    }
    """

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
        if event.data_table.id == "jobs-table":
            self._selected_job_id = event.row_key.value
            self._set_status(f"Selected job {self._selected_job_id}")
        elif event.data_table.id == "recordings-table":
            self._selected_audio_track_id = event.row_key.value
            self._set_status(f"Selected recording {self._selected_audio_track_id}")

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
                message = _sync_result_status(event.worker.result)
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
        self._reset_table(
            "jobs-table",
            ("ID", "Status", "Transcript", "Recap", "Updated"),
        )
        self._reset_table(
            "recordings-table",
            ("ID", "Title", "Duration", "Transcript", "Recap"),
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
        jobs_by_track = {str(job.audio_track_id): job for job in jobs}
        audio_track_ids = {str(audio_track.id) for audio_track in audio_tracks}
        self._selected_audio_track_id = (
            self._selected_audio_track_id
            if self._selected_audio_track_id in audio_track_ids
            else None
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
            ("ID", "Title", "Duration", "Transcript", "Recap"),
        )
        for audio_track in audio_tracks:
            job = jobs_by_track.get(str(audio_track.id))
            recordings_table.add_row(
                str(audio_track.id),
                audio_track.title or audio_track.artifact.uri,
                _format_duration(audio_track.metadata),
                "yes" if job and job.transcript_id else "no",
                "yes" if job and job.recap_id else "no",
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
        for column in columns:
            table.add_column(column)
        return table

    def _create_campaign(self, name: str | None) -> None:
        if not name:
            return
        try:
            result = self.runtime.use_cases.create_campaign.execute(
                CreateCampaignCommand(name=name),
            )
            self._selected_campaign_id = str(result.campaign.id)
            self.refresh_dashboard()
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))

    def _add_participant(self, campaign_id: str, display_name: str | None) -> None:
        if not display_name:
            return
        try:
            self.runtime.use_cases.add_participant.execute(
                AddParticipantToCampaignCommand(
                    campaign_id=campaign_id,
                    display_name=display_name,
                ),
            )
            self.refresh_dashboard()
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))

    def _open_add_sample(self, campaign_id: str) -> None:
        participants = self.runtime.use_cases.list_participants.execute(
            ListParticipantsCommand(campaign_id=campaign_id),
        ).participants
        self.push_screen(
            VoiceSampleScreen(
                runtime=self.runtime,
                campaign_id=campaign_id,
                participants=tuple((p.display_name, str(p.id)) for p in participants),
            ),
            lambda completed: self.refresh_dashboard() if completed else None,
        )

    def _open_submit_recording(self, campaign_id: str) -> None:
        self.push_screen(
            RecordingScreen(self.runtime, campaign_id),
            lambda completed: self.refresh_dashboard() if completed else None,
        )

    def _open_review(self, campaign_id: str) -> None:
        job = self._selected_job()
        if job is None:
            self._set_status("Select a job")
            return
        if job.status is not JobStatus.WAITING_FOR_REVIEW:
            self._set_status("Job is not waiting for review")
            return

        participants = self.runtime.use_cases.list_participants.execute(
            ListParticipantsCommand(campaign_id=campaign_id),
        ).participants
        self.push_screen(
            ReviewMappingsScreen(job, participants),
            lambda mappings: self._review_selected_job(tuple(mappings or ())),
        )

    def _run_selected_job(self) -> None:
        job = self._selected_job()
        if job is None:
            self._set_status("Select a job")
            return
        self.run_worker(
            lambda: self.runtime.use_cases.run_processing_job.execute(
                RunProcessingJobCommand(job_id=str(job.id)),
            ),
            group="job",
            thread=True,
            exit_on_error=False,
        )

    def _create_job_for_selected_audio_track(self) -> None:
        if self._selected_audio_track_id is None:
            self._set_status("Select a recording")
            return

        try:
            result = (
                self.runtime.use_cases.create_processing_job_for_audio_track.execute(
                    CreateProcessingJobForAudioTrackCommand(
                        audio_track_id=self._selected_audio_track_id,
                    ),
                )
            )
            self.refresh_dashboard(update_campaigns=False)
            self._selected_job_id = str(result.job.id)
            self._set_status(f"Created job {result.job.id}")
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))

    def _sync_campaign_folder(self, campaign_id: str) -> None:
        self.run_worker(
            lambda: self.runtime.use_cases.sync_campaign_folder.execute(
                SyncCampaignFolderCommand(campaign_id=campaign_id),
            ),
            group="sync",
            thread=True,
            exit_on_error=False,
        )

    def _review_selected_job(self, mappings: tuple[ManualSpeakerMappingCommand, ...]) -> None:
        job = self._selected_job()
        if job is None or not mappings:
            return
        self.run_worker(
            lambda: self.runtime.use_cases.review_speaker_mappings.execute(
                ReviewSpeakerMappingsCommand(
                    job_id=str(job.id),
                    mappings=mappings,
                ),
            ),
            group="review",
            thread=True,
            exit_on_error=False,
        )

    def _preview_transcript(self) -> None:
        job = self._selected_job()
        if job is None or job.transcript_id is None:
            self._set_status("No transcript")
            return
        try:
            result = self.runtime.use_cases.preview_transcript_markdown.execute(
                PreviewTranscriptMarkdownCommand(transcript_id=str(job.transcript_id)),
            )
            self.push_screen(MarkdownPreviewScreen("Transcript", result.markdown))
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))

    def _preview_recap(self) -> None:
        job = self._selected_job()
        if job is None or job.recap_id is None:
            self._set_status("No recap")
            return
        try:
            result = self.runtime.use_cases.preview_recap_markdown.execute(
                PreviewRecapMarkdownCommand(recap_id=str(job.recap_id)),
            )
            self.push_screen(MarkdownPreviewScreen("Recap", result.markdown))
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))

    def _export_transcript(self) -> None:
        job = self._selected_job()
        if job is None or job.transcript_id is None:
            self._set_status("No transcript")
            return
        try:
            result = self.runtime.use_cases.export_transcript_markdown.execute(
                ExportTranscriptMarkdownCommand(transcript_id=str(job.transcript_id)),
            )
            location = self.runtime.format_artifact_location(result.artifact)
            self.copy_to_clipboard(location)
            self._set_status(location)
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))

    def _export_recap(self) -> None:
        job = self._selected_job()
        if job is None or job.recap_id is None:
            self._set_status("No recap")
            return
        try:
            result = self.runtime.use_cases.export_recap_markdown.execute(
                ExportRecapMarkdownCommand(recap_id=str(job.recap_id)),
            )
            location = self.runtime.format_artifact_location(result.artifact)
            self.copy_to_clipboard(location)
            self._set_status(location)
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))

    def _open_diagnostics(self) -> None:
        self.push_screen(
            DiagnosticsScreen(
                self.runtime.diagnostics(self._selected_campaign_id),
            ),
        )

    def _selected_job(self):
        if self._selected_job_id is None:
            return None
        try:
            return self.runtime.use_cases.get_job_status.execute(
                GetJobStatusCommand(job_id=self._selected_job_id),
            ).job
        except (ApplicationError, DomainError, ValueError):
            return None

    def _with_campaign(self, action) -> None:
        if self._selected_campaign_id is None:
            self._set_status("Select a campaign")
            return
        action(self._selected_campaign_id)

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _progress(self) -> ProgressBar:
        return self.query_one("#job-progress", ProgressBar)


class CreateCampaignScreen(ModalScreen[str | None]):
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("New Campaign")
            yield Input(placeholder="Name", id="name")
            yield Button("Create", id="create", variant="primary")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            self.dismiss(self.query_one("#name", Input).value.strip())
        else:
            self.dismiss(None)


class AddParticipantScreen(ModalScreen[str | None]):
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Add Player")
            yield Input(placeholder="Display name", id="display-name")
            yield Button("Add", id="add", variant="primary")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add":
            self.dismiss(self.query_one("#display-name", Input).value.strip())
        else:
            self.dismiss(None)


class VoiceSampleScreen(ModalScreen[bool]):
    def __init__(
        self,
        runtime: InterfaceRuntime,
        campaign_id: str,
        participants: tuple[tuple[str, str], ...],
    ) -> None:
        super().__init__()
        self.runtime = runtime
        self.campaign_id = campaign_id
        self.participants = participants
        self._preflight_ok = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Voice Sample")
            yield Select(self.participants, prompt="Player", id="participant")
            yield Input(
                placeholder="campaign-1/players/Alice/sample.wav",
                id="artifact-uri",
            )
            yield Static("No metadata", id="metadata", classes="metadata")
            yield Button("Preflight", id="preflight")
            yield Button("Save", id="save", variant="primary", disabled=True)
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "preflight":
            self._run_preflight()
        elif event.button.id == "save":
            self._save()
        else:
            self.dismiss(False)

    def _run_preflight(self) -> None:
        uri = self.query_one("#artifact-uri", Input).value.strip()
        try:
            result = self.runtime.use_cases.inspect_audio_metadata.execute(
                InspectAudioMetadataCommand(artifact_uri=uri),
            )
            self.query_one("#metadata", Static).update(_metadata_text(result.metadata))
            self.query_one("#save", Button).disabled = False
            self._preflight_ok = True
        except (ApplicationError, DomainError, ValueError) as exc:
            self.query_one("#metadata", Static).update(str(exc))
            self.query_one("#save", Button).disabled = True
            self._preflight_ok = False

    def _save(self) -> None:
        participant_id = self.query_one("#participant", Select).value
        uri = self.query_one("#artifact-uri", Input).value.strip()
        if participant_id in (Select.BLANK, Select.NULL) or not self._preflight_ok:
            return
        try:
            self.runtime.use_cases.add_voice_sample.execute(
                AddVoiceSampleCommand(
                    campaign_id=self.campaign_id,
                    participant_id=str(participant_id),
                    artifact_uri=uri,
                ),
            )
            self.dismiss(True)
        except (ApplicationError, DomainError, ValueError) as exc:
            self.query_one("#metadata", Static).update(str(exc))


class RecordingScreen(ModalScreen[bool]):
    def __init__(self, runtime: InterfaceRuntime, campaign_id: str) -> None:
        super().__init__()
        self.runtime = runtime
        self.campaign_id = campaign_id
        self._preflight_ok = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Recording")
            yield Input(placeholder="Artifact URI", id="artifact-uri")
            yield Input(placeholder="Title", id="title")
            yield Static("No metadata", id="metadata", classes="metadata")
            yield Button("Preflight", id="preflight")
            yield Button("Submit", id="submit", variant="primary", disabled=True)
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "preflight":
            self._run_preflight()
        elif event.button.id == "submit":
            self._submit()
        else:
            self.dismiss(False)

    def _run_preflight(self) -> None:
        uri = self.query_one("#artifact-uri", Input).value.strip()
        try:
            result = self.runtime.use_cases.inspect_audio_metadata.execute(
                InspectAudioMetadataCommand(artifact_uri=uri),
            )
            self.query_one("#metadata", Static).update(_metadata_text(result.metadata))
            self.query_one("#submit", Button).disabled = False
            self._preflight_ok = True
        except (ApplicationError, DomainError, ValueError) as exc:
            self.query_one("#metadata", Static).update(str(exc))
            self.query_one("#submit", Button).disabled = True
            self._preflight_ok = False

    def _submit(self) -> None:
        uri = self.query_one("#artifact-uri", Input).value.strip()
        title = self.query_one("#title", Input).value.strip() or None
        if not self._preflight_ok:
            return
        try:
            self.runtime.use_cases.submit_recording_for_processing.execute(
                SubmitRecordingForProcessingCommand(
                    campaign_id=self.campaign_id,
                    artifact_uri=uri,
                    title=title,
                ),
            )
            self.dismiss(True)
        except (ApplicationError, DomainError, ValueError) as exc:
            self.query_one("#metadata", Static).update(str(exc))


class ReviewMappingsScreen(ModalScreen[tuple[ManualSpeakerMappingCommand, ...] | None]):
    def __init__(self, job, participants) -> None:
        super().__init__()
        self.job = job
        self.participants = participants

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Review Mapping")
            yield Static(_participants_text(self.participants), classes="metadata")
            yield Static(_warnings_text(self.job), classes="metadata")
            yield TextArea("", id="mappings", language="text")
            yield Button("Submit", id="submit", variant="primary")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "submit":
            self.dismiss(None)
            return

        try:
            mappings = tuple(
                _parse_mapping(line)
                for line in self.query_one("#mappings", TextArea).text.splitlines()
                if line.strip()
            )
        except ValueError:
            self.dismiss(None)
            return
        self.dismiss(mappings)


class MarkdownPreviewScreen(ModalScreen[None]):
    def __init__(self, title: str, markdown: str) -> None:
        super().__init__()
        self.title = title
        self.markdown = markdown

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label(self.title)
            yield Markdown(self.markdown, id="preview-markdown")
            yield Button("Close", id="close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class DiagnosticsScreen(ModalScreen[None]):
    def __init__(self, diagnostics: RuntimeDiagnostics) -> None:
        super().__init__()
        self.diagnostics = diagnostics

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Diagnostics")
            yield Static(_diagnostics_text(self.diagnostics), classes="metadata")
            yield Button("Close", id="close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


def _format_duration(metadata: AudioMetadata) -> str:
    return f"{metadata.duration_seconds:.2f}s"


def _metadata_text(metadata: AudioMetadata) -> str:
    lines = [f"duration: {_format_duration(metadata)}"]
    if metadata.format:
        lines.append(f"format: {metadata.format}")
    if metadata.codec:
        lines.append(f"codec: {metadata.codec}")
    if metadata.sample_rate_hz:
        lines.append(f"sample rate: {metadata.sample_rate_hz} Hz")
    if metadata.channels:
        lines.append(f"channels: {metadata.channels}")
    if metadata.file_size_bytes is not None:
        lines.append(f"size: {metadata.file_size_bytes} bytes")
    return "\n".join(lines)


def _parse_mapping(value: str) -> ManualSpeakerMappingCommand:
    try:
        anonymous_label, participant_id = value.split("=", 1)
    except ValueError as exc:
        raise ValueError("mapping must use SPEAKER_00=participant-id form") from exc

    anonymous_label = anonymous_label.strip()
    participant_id = participant_id.strip()
    if not anonymous_label or not participant_id:
        raise ValueError("mapping must include speaker label and participant id")

    return ManualSpeakerMappingCommand(
        anonymous_label=anonymous_label,
        participant_id=participant_id,
        confidence=1.0,
    )


def _participants_text(participants) -> str:
    return "\n".join(
        f"{participant.id}: {participant.display_name}" for participant in participants
    )


def _warnings_text(job) -> str:
    lines = [f"{warning.kind.value}: {warning.message}" for warning in job.warnings]
    if job.error_message:
        lines.append(f"error: {job.error_message}")
    return "\n".join(lines) if lines else "No warnings"


def _sync_result_status(result) -> str:
    return (
        "Synced: "
        f"players +{result.participants_created}, "
        f"samples +{result.voice_samples_added}/~{result.voice_samples_updated}"
        f"/-{result.voice_samples_deleted}, "
        f"records +{result.audio_tracks_added}/~{result.audio_tracks_updated}"
        f"/-{result.audio_tracks_deleted}, "
        f"pending jobs -{result.pending_jobs_deleted}"
    )


def _diagnostics_text(diagnostics: RuntimeDiagnostics) -> str:
    lines = [
        f"storage root: {diagnostics.storage_root}",
        f"sqlite path: {diagnostics.sqlite_path}",
        f"processing work root: {diagnostics.processing_work_root}",
        f"recap prompts file: {diagnostics.recap_prompts_file}",
        f"whisperx model: {diagnostics.whisperx_model_name}",
        f"whisperx device: {diagnostics.whisperx_device}",
        f"whisperx compute type: {diagnostics.whisperx_compute_type}",
        f"deepseek configured: {diagnostics.deepseek_configured}",
        f"huggingface configured: {diagnostics.huggingface_configured}",
    ]
    lines.extend(f"recent: {message}" for message in diagnostics.recent_messages)
    return "\n".join(lines)


def run_tui(runtime: InterfaceRuntime) -> None:
    NoteKeeperTui(runtime).run()
