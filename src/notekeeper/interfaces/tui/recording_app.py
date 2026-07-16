"""Recording actions and modal screen for the Textual interface."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from notekeeper.application import (
    ApplicationError,
    InspectAudioMetadataCommand,
    SubmitRecordingForProcessingCommand,
)
from notekeeper.domain import DomainError

from .common import metadata_text


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
