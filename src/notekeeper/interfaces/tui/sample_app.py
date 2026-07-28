"""Voice sample actions and modal screen for the Textual interface."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select, Static

from notekeeper.application import (
    AddVoiceSampleCommand,
    ApplicationError,
    DeleteVoiceSampleCommand,
    InspectLocalAudioFileCommand,
    ListParticipantsCommand,
    ListVoiceSamplesCommand,
)
from notekeeper.domain import DomainError, Participant

from .audio_file_explorer_screen import AudioFileExplorerScreen
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
        self._source_path: Path | None = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Voice Sample")
            yield Select(self.participants, prompt="Player", id="participant")
            yield Static(
                "No file selected",
                id="source-path",
                classes="selected-file",
            )
            yield Button("Choose File", id="choose-file")
            yield Static("No metadata", id="metadata", classes="metadata")
            yield Button("Save", id="save", variant="primary", disabled=True)
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "choose-file":
            self.app.push_screen(
                AudioFileExplorerScreen(),
                self._select_source,
            )
        elif event.button.id == "save":
            self._save()
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
            self.query_one("#save", Button).disabled = False
            self._preflight_ok = True
        except (ApplicationError, DomainError, ValueError) as exc:
            self.query_one("#metadata", Static).update(str(exc))
            self.query_one("#save", Button).disabled = True
            self._preflight_ok = False

    def _save(self) -> None:
        participant_id = self.query_one("#participant", Select).value
        if (
            participant_id in (Select.BLANK, Select.NULL)
            or not self._preflight_ok
            or self._source_path is None
        ):
            return
        try:
            self.runtime.use_cases.add_voice_sample.execute(
                AddVoiceSampleCommand(
                    campaign_id=self.campaign_id,
                    participant_id=str(participant_id),
                    source_path=str(self._source_path),
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
