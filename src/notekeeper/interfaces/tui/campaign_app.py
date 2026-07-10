"""Campaign actions and modal screen for the Textual interface."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from notekeeper.application import ApplicationError, CreateCampaignCommand, SyncCampaignFolderCommand
from notekeeper.domain import DomainError


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


def create_campaign(app, name: str | None) -> None:
    if not name:
        return
    try:
        result = app.runtime.use_cases.create_campaign.execute(
            CreateCampaignCommand(name=name),
        )
        app._selected_campaign_id = str(result.campaign.id)
        app.refresh_dashboard()
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))


def sync_campaign_folder(app, campaign_id: str) -> None:
    app.run_worker(
        lambda: app.runtime.use_cases.sync_campaign_folder.execute(
            SyncCampaignFolderCommand(campaign_id=campaign_id),
        ),
        group="sync",
        thread=True,
        exit_on_error=False,
    )
