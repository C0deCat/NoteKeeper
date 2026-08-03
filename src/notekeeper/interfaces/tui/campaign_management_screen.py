"""Campaign management modal for the Textual interface."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static

from notekeeper.application import (
    ApplicationError,
    CreateCampaignCommand,
    DeleteCampaignCommand,
    ListCampaignsCommand,
    UpdateCampaignCommand,
)
from notekeeper.domain import Campaign, DomainError

from ..contracts import InterfaceRuntime
from .campaign_deletion_screen import CampaignDeletionScreen
from .identifier_data_table import IdentifierDataTable


class ManageCampaignsScreen(ModalScreen[str | None]):
    """Create, rename, and delete campaigns in one modal."""

    def __init__(
        self,
        runtime: InterfaceRuntime,
        selected_campaign_id: str | None,
    ) -> None:
        super().__init__()
        self._runtime = runtime
        self._campaigns_by_id: dict[str, Campaign] = {}
        self._selected_campaign_id = selected_campaign_id

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Manage Campaigns")
            yield IdentifierDataTable(id="campaigns-table")
            yield Input(placeholder="Campaign name", id="campaign-name")
            yield Static("", id="campaign-management-status")
            with Horizontal():
                yield Button("Create", id="create", variant="primary")
                yield Button("Rename", id="rename")
                yield Button("Delete", id="delete", variant="error")
                yield Button("Close", id="close")

    def on_mount(self) -> None:
        self._refresh_campaigns()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._select_campaign(event.data_table, event.row_key)

    def on_data_table_row_highlighted(
        self,
        event: DataTable.RowHighlighted,
    ) -> None:
        self._select_campaign(event.data_table, event.row_key)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "campaign-name":
            self._update_action_buttons()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            self._create_campaign()
        elif event.button.id == "rename":
            self._rename_campaign()
        elif event.button.id == "delete":
            self._confirm_delete_campaign()
        elif event.button.id == "close":
            self.dismiss(self._selected_campaign_id)

    def _refresh_campaigns(self) -> None:
        try:
            campaigns = self._runtime.use_cases.list_campaigns.execute(
                ListCampaignsCommand(),
            ).campaigns
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))
            return

        self._campaigns_by_id = {str(campaign.id): campaign for campaign in campaigns}
        if self._selected_campaign_id not in self._campaigns_by_id:
            self._selected_campaign_id = (
                str(campaigns[0].id) if campaigns else None
            )

        table = self.query_one("#campaigns-table", IdentifierDataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.add_column("ID")
        table.add_column("Name")
        for campaign in campaigns:
            table.add_identifier_row(
                str(campaign.id),
                campaign.name,
                identifier_indices=(0,),
                key=str(campaign.id),
            )

        if self._selected_campaign_id is not None:
            table.move_cursor(row=table.get_row_index(self._selected_campaign_id))
        self._sync_name_input()
        self._update_action_buttons()

    def _select_campaign(
        self,
        table: DataTable[object],
        row_key: object,
    ) -> None:
        if table.id != "campaigns-table":
            return
        self._selected_campaign_id = str(getattr(row_key, "value", row_key))
        self._sync_name_input()
        self._update_action_buttons()

    def _sync_name_input(self) -> None:
        campaign = self._campaigns_by_id.get(self._selected_campaign_id or "")
        self.query_one("#campaign-name", Input).value = (
            campaign.name if campaign is not None else ""
        )

    def _create_campaign(self) -> None:
        name = self._campaign_name()
        if not name:
            return
        try:
            campaign = self._runtime.use_cases.create_campaign.execute(
                CreateCampaignCommand(name=name),
            ).campaign
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))
            return

        self._selected_campaign_id = str(campaign.id)
        self._set_status(f"Created campaign {campaign.name}")
        self._refresh_campaigns()

    def _rename_campaign(self) -> None:
        campaign_id = self._selected_campaign_id
        name = self._campaign_name()
        if campaign_id is None or not name:
            return
        try:
            campaign = self._runtime.use_cases.update_campaign.execute(
                UpdateCampaignCommand(campaign_id=campaign_id, name=name),
            ).campaign
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))
            return

        self._set_status(f"Renamed campaign to {campaign.name}")
        self._refresh_campaigns()

    def _confirm_delete_campaign(self) -> None:
        campaign = self._campaigns_by_id.get(self._selected_campaign_id or "")
        if campaign is None:
            return
        self.app.push_screen(
            CampaignDeletionScreen(campaign.name),
            self._delete_campaign,
        )

    def _delete_campaign(self, delete_files: bool | None) -> None:
        campaign_id = self._selected_campaign_id
        if campaign_id is None or delete_files is None:
            return
        try:
            self._runtime.use_cases.delete_campaign.execute(
                DeleteCampaignCommand(
                    campaign_id=campaign_id,
                    delete_files=delete_files,
                ),
            )
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))
            return

        self._set_status("Deleted campaign")
        self._selected_campaign_id = None
        self._refresh_campaigns()

    def _campaign_name(self) -> str:
        return self.query_one("#campaign-name", Input).value.strip()

    def _update_action_buttons(self) -> None:
        name_present = bool(self._campaign_name())
        campaign_selected = self._selected_campaign_id is not None
        self.query_one("#create", Button).disabled = not name_present
        self.query_one("#rename", Button).disabled = not (
            campaign_selected and name_present
        )
        self.query_one("#delete", Button).disabled = not campaign_selected

    def _set_status(self, message: str) -> None:
        self.query_one("#campaign-management-status", Static).update(message)
