"""Recording actions and modal screen for the Textual interface."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from notekeeper.application import (
    ApplicationError,
    DeleteAudioTrackCommand,
    InspectAudioMetadataCommand,
    SubmitRecordingForProcessingCommand,
    UpdateAudioTrackCommand,
)
from notekeeper.domain import AudioTrack, DomainError

from .common import metadata_text
from .object_action_confirmation_screen import ObjectActionConfirmationScreen
from .rename_screen import RenameScreen


class RecordingScreen(ModalScreen[bool]):
    def __init__(self, runtime, campaign_id: str) -> None:
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
            self.query_one("#metadata", Static).update(metadata_text(result.metadata))
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
