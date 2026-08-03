"""Participant actions and modal screen for the Textual interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from notekeeper.application import (
    AddParticipantToCampaignCommand,
    ApplicationError,
    DeleteParticipantCommand,
    UpdateParticipantCommand,
)
from notekeeper.domain import DomainError, Participant

from .object_action_confirmation_screen import ObjectActionConfirmationScreen
from .rename_screen import RenameScreen

if TYPE_CHECKING:
    from .tui import NoteKeeperTui


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


def add_participant(
    app: NoteKeeperTui,
    campaign_id: str,
    display_name: str | None,
) -> None:
    if not display_name:
        return
    try:
        app.runtime.use_cases.add_participant.execute(
            AddParticipantToCampaignCommand(
                campaign_id=campaign_id,
                display_name=display_name,
            ),
        )
        app.refresh_dashboard(update_campaigns=False)
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))


def open_rename_participant(
    app: NoteKeeperTui,
    participant: Participant,
) -> None:
    app.push_screen(
        RenameScreen("Rename Player", participant.display_name),
        lambda name: _rename_participant(app, participant, name),
    )


def _rename_participant(
    app: NoteKeeperTui,
    participant: Participant,
    name: str | None,
) -> None:
    if not name:
        return
    try:
        app.runtime.use_cases.update_participant.execute(
            UpdateParticipantCommand(
                campaign_id=str(participant.campaign_id),
                participant_id=str(participant.id),
                display_name=name,
            ),
        )
        app.refresh_dashboard(update_campaigns=False)
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))


def confirm_remove_participant(
    app: NoteKeeperTui,
    participant: Participant,
) -> None:
    app.push_screen(
        ObjectActionConfirmationScreen("player", participant.display_name),
        lambda confirmed: _remove_participant(app, participant, confirmed),
    )


def _remove_participant(
    app: NoteKeeperTui,
    participant: Participant,
    confirmed: bool | None,
) -> None:
    if not confirmed:
        return
    try:
        app.runtime.use_cases.delete_participant.execute(
            DeleteParticipantCommand(
                campaign_id=str(participant.campaign_id),
                participant_id=str(participant.id),
            ),
        )
        app.refresh_dashboard(update_campaigns=False)
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))
