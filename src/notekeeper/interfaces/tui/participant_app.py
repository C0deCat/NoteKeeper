"""Participant actions and modal screen for the Textual interface."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from notekeeper.application import AddParticipantToCampaignCommand, ApplicationError
from notekeeper.domain import DomainError


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


def add_participant(app, campaign_id: str, display_name: str | None) -> None:
    if not display_name:
        return
    try:
        app.runtime.use_cases.add_participant.execute(
            AddParticipantToCampaignCommand(
                campaign_id=campaign_id,
                display_name=display_name,
            ),
        )
        app.refresh_dashboard()
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))
