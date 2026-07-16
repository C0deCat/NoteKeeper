"""Confirmation screen for destructive campaign deletion."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class CampaignDeletionScreen(ModalScreen[bool | None]):
    """Let the user choose whether campaign files are removed too."""

    def __init__(self, campaign_name: str) -> None:
        super().__init__()
        self._campaign_name = campaign_name

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label(f"Delete campaign: {self._campaign_name}")
            yield Label("This action cannot be undone.")
            yield Button("Delete from database only", id="database-only")
            yield Button(
                "Delete campaign and files",
                id="campaign-and-files",
                variant="error",
            )
            yield Button("Cancel", id="cancel", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "database-only":
            self.dismiss(False)
        elif event.button.id == "campaign-and-files":
            self.dismiss(True)
        else:
            self.dismiss(None)
