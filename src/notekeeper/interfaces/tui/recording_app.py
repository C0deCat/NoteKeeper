"""Recording actions and modal screen for the Textual interface."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from textual.worker import Worker, WorkerState

from notekeeper.application import (
    ApplicationError,
    DeleteAudioTrackCommand,
    InspectLocalAudioFileCommand,
    SubmitRecordingForProcessingCommand,
    UpdateAudioTrackCommand,
)
from notekeeper.domain import AudioTrack, DomainError

from .audio_file_explorer_screen import AudioFileExplorerScreen
from .common import metadata_text
from .object_action_confirmation_screen import ObjectActionConfirmationScreen
from .rename_screen import RenameScreen


class RecordingScreen(ModalScreen[bool]):
    def __init__(self, runtime, campaign_id: str) -> None:
        super().__init__()
        self.runtime = runtime
        self.campaign_id = campaign_id
        self._preflight_ok = False
        self._source_path: Path | None = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Recording")
            yield Static(
                "No file selected",
                id="source-path",
                classes="selected-file",
            )
            yield Button("Choose File", id="choose-file")
            yield Input(placeholder="Title", id="title")
            yield Static("No metadata", id="metadata", classes="metadata")
            yield Button("Submit", id="submit", variant="primary", disabled=True)
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "choose-file":
            self.app.push_screen(
                AudioFileExplorerScreen(),
                self._select_source,
            )
        elif event.button.id == "submit":
            self._submit()
        else:
            self.dismiss(False)

    def _select_source(self, source_path: Path | None) -> None:
        if source_path is None:
            return
        self._source_path = source_path.resolve(strict=False)
        self.query_one("#source-path", Static).update(str(self._source_path))
        self._run_preflight()

    def _run_preflight(self) -> None:
        if self._source_path is None:
            return
        try:
            result = self.runtime.use_cases.inspect_local_audio_file.execute(
                InspectLocalAudioFileCommand(source_path=str(self._source_path)),
            )
            self._source_path = Path(result.source_path)
            self.query_one("#source-path", Static).update(result.source_path)
            self.query_one("#metadata", Static).update(metadata_text(result.metadata))
            self.query_one("#submit", Button).disabled = False
            self._preflight_ok = True
        except (ApplicationError, DomainError, ValueError) as exc:
            self.query_one("#metadata", Static).update(str(exc))
            self.query_one("#submit", Button).disabled = True
            self._preflight_ok = False

    def _submit(self) -> None:
        title = self.query_one("#title", Input).value.strip() or None
        if not self._preflight_ok or self._source_path is None:
            return
        self.query_one("#submit", Button).disabled = True
        self.query_one("#choose-file", Button).disabled = True
        self.query_one("#metadata", Static).update("Normalizing…")
        self.run_worker(
            lambda: self.runtime.use_cases.submit_recording_for_processing.execute(
                SubmitRecordingForProcessingCommand(
                    campaign_id=self.campaign_id,
                    source_path=str(self._source_path),
                    title=title,
                ),
            ),
            group="recording-normalize",
            thread=True,
            exit_on_error=False,
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.group != "recording-normalize":
            return
        if event.state is WorkerState.SUCCESS:
            result = event.worker.result
            cleanup_warnings = getattr(result, "cleanup_warnings", ())
            if cleanup_warnings:
                self.app.notify(
                    "\n".join(cleanup_warnings),
                    severity="warning",
                )
            self.dismiss(True)
        elif event.state is WorkerState.ERROR:
            error = event.worker.error
            self.query_one("#metadata", Static).update(
                str(error) if error is not None else "Recording normalization failed",
            )
            self.query_one("#submit", Button).disabled = False
            self.query_one("#choose-file", Button).disabled = False


def open_submit_recording(app, campaign_id: str) -> None:
    app.push_screen(
        RecordingScreen(app.runtime, campaign_id),
        lambda completed: (
            app.refresh_dashboard(update_campaigns=False) if completed else None
        ),
    )


def open_rename_recording(app, audio_track: AudioTrack) -> None:
    current_name = audio_track.title or audio_track.artifact.uri
    app.push_screen(
        RenameScreen("Rename Recording", current_name),
        lambda name: _rename_recording(app, audio_track, name),
    )


def _rename_recording(
    app,
    audio_track: AudioTrack,
    name: str | None,
) -> None:
    if not name:
        return
    try:
        app.runtime.use_cases.update_audio_track.execute(
            UpdateAudioTrackCommand(
                campaign_id=str(audio_track.campaign_id),
                audio_track_id=str(audio_track.id),
                artifact_uri=audio_track.artifact.uri,
                artifact_kind=audio_track.artifact.kind,
                title=name,
            ),
        )
        app.refresh_dashboard(update_campaigns=False)
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))


def confirm_remove_recording(app, audio_track: AudioTrack) -> None:
    name = audio_track.title or audio_track.artifact.uri
    app.push_screen(
        ObjectActionConfirmationScreen("recording", name),
        lambda confirmed: _remove_recording(app, audio_track, confirmed),
    )


def _remove_recording(
    app,
    audio_track: AudioTrack,
    confirmed: bool,
) -> None:
    if not confirmed:
        return
    try:
        app.runtime.use_cases.delete_audio_track.execute(
            DeleteAudioTrackCommand(
                campaign_id=str(audio_track.campaign_id),
                audio_track_id=str(audio_track.id),
            ),
        )
        app.refresh_dashboard(update_campaigns=False)
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))
