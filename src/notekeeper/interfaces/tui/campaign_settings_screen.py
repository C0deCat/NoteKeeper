"""Campaign-specific settings menu for the Textual interface."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Select, Static

from notekeeper.application import ListCampaignsCommand

from ..contracts import InterfaceRuntime
from .modal_body import ModalBody
from .modal_header import ModalHeader
from .recap_prompt_editor_screen import RecapPromptEditorScreen
from .settings_confirmation_screen import SettingsConfirmationScreen


class CampaignSettingsScreen(ModalScreen[None]):
    def __init__(
        self,
        runtime: InterfaceRuntime,
        campaign_id: str | None,
        campaign_name: str | None,
    ) -> None:
        super().__init__()
        self._runtime = runtime
        self._campaign_id = campaign_id
        self._campaign_name = campaign_name
        self._campaigns = self._runtime.use_cases.campaigns.list.execute(
            ListCampaignsCommand()
        ).campaigns

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal settings-menu"):
            yield ModalHeader("Campaign Settings", close=True)
            with ModalBody(classes="modal-body"):
                yield Select(
                    ((campaign.name, str(campaign.id)) for campaign in self._campaigns),
                    value=(
                        self._campaign_id
                        if self._campaign_id is not None
                        else Select.NULL
                    ),
                    prompt="Campaign",
                    id="settings-campaign-select",
                )
                yield Static(
                    self._campaign_name or "Select a campaign",
                    id="campaign-settings-name",
                )
                disabled = self._campaign_id is None
                yield Button(
                    "Chunk Recap Prompt",
                    id="chunk-recap-prompt",
                    disabled=disabled,
                )
                yield Button(
                    "Combined Recap Prompt",
                    id="combined-recap-prompt",
                    disabled=disabled,
                )
                yield Button(
                    "Reset Prompts",
                    id="reset-prompts",
                    variant="warning",
                    disabled=disabled,
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "chunk-recap-prompt":
            self._open_editor("chunk")
        elif event.button.id == "combined-recap-prompt":
            self._open_editor("combined")
        elif event.button.id == "close":
            self.dismiss(None)
        elif event.button.id == "reset-prompts":
            self.app.push_screen(
                SettingsConfirmationScreen(
                    "Reset campaign recap prompts to the platform template?",
                    "Reset",
                ),
                self._reset_prompts,
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "settings-campaign-select":
            return
        if event.value in (Select.NULL, Select.BLANK):
            self._campaign_id = None
            self._campaign_name = None
        else:
            self._campaign_id = str(event.value)
            campaign = next(
                item for item in self._campaigns if str(item.id) == self._campaign_id
            )
            self._campaign_name = campaign.name
        self.query_one("#campaign-settings-name", Static).update(
            self._campaign_name or "Select a campaign"
        )
        disabled = self._campaign_id is None
        for selector in (
            "#chunk-recap-prompt",
            "#combined-recap-prompt",
            "#reset-prompts",
        ):
            self.query_one(selector, Button).disabled = disabled

    def _open_editor(self, prompt_kind: str) -> None:
        if self._campaign_id is None or self._campaign_name is None:
            return
        self.app.push_screen(
            RecapPromptEditorScreen(
                self._runtime,
                self._campaign_id,
                self._campaign_name,
                prompt_kind,
            ),
        )

    def _reset_prompts(self, confirmed: bool | None) -> None:
        if not confirmed or self._campaign_id is None:
            return
        service = self._runtime.use_cases.settings
        if service is None:
            return
        service.reset_campaign(self._campaign_id)
        self.notify("Campaign prompts reset")


__all__ = ["CampaignSettingsScreen"]
