"""Voice sample actions and modal screen for the Textual interface."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from notekeeper.application import (
    AddVoiceSampleCommand,
    ApplicationError,
    DeleteVoiceSampleCommand,
    InspectAudioMetadataCommand,
    ListParticipantsCommand,
    ListVoiceSamplesCommand,
)
from notekeeper.domain import DomainError, Participant

from .common import metadata_text
from .remove_voice_sample_screen import RemoveVoiceSampleScreen


class VoiceSampleScreen(ModalScreen[bool]):
    def __init__(
        self,
        runtime,
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
            self.query_one("#metadata", Static).update(metadata_text(result.metadata))
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


def open_add_sample(app, campaign_id: str) -> None:
    participants = app.runtime.use_cases.list_participants.execute(
        ListParticipantsCommand(campaign_id=campaign_id),
    ).participants
    app.push_screen(
        VoiceSampleScreen(
            runtime=app.runtime,
            campaign_id=campaign_id,
            participants=tuple((p.display_name, str(p.id)) for p in participants),
        ),
        lambda completed: (
            app.refresh_dashboard(update_campaigns=False) if completed else None
        ),
    )


def open_remove_sample(app, participant: Participant) -> None:
    try:
        samples = app.runtime.use_cases.list_voice_samples.execute(
            ListVoiceSamplesCommand(
                campaign_id=str(participant.campaign_id),
                participant_id=str(participant.id),
            ),
        ).voice_samples
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))
        return

    if not samples:
        app._set_status(f"Player {participant.display_name} has no voice samples")
        app._update_action_buttons()
        return
    app.push_screen(
        RemoveVoiceSampleScreen(samples),
        lambda sample_id: _remove_sample(app, participant, sample_id),
    )


def _remove_sample(
    app,
    participant: Participant,
    sample_id: str | None,
) -> None:
    if sample_id is None:
        return
    try:
        app.runtime.use_cases.delete_voice_sample.execute(
            DeleteVoiceSampleCommand(
                campaign_id=str(participant.campaign_id),
                voice_sample_id=sample_id,
            ),
        )
        app.refresh_dashboard(update_campaigns=False)
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))
