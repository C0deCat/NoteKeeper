"""First-level settings category menu."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ..contracts import InterfaceRuntime
from .campaign_settings_screen import CampaignSettingsScreen
from .modal_body import ModalBody
from .modal_header import ModalHeader
from .user_settings_screen import UserSettingsScreen
from .workspace_settings_screen import WorkspaceSettingsScreen


class SettingsScreen(ModalScreen[None]):
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

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal settings-menu"):
            yield ModalHeader("Settings", close=True)
            with ModalBody(classes="modal-body"):
                yield Button("Workspace", id="workspace-settings")
                yield Button("Campaign", id="campaign-settings")
                yield Button("User", id="user-settings")
                yield Static("", id="settings-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "workspace-settings":
            self.app.push_screen(WorkspaceSettingsScreen(self._runtime))
        elif event.button.id == "campaign-settings":
            self.app.push_screen(
                CampaignSettingsScreen(
                    self._runtime,
                    self._campaign_id,
                    self._campaign_name,
                )
            )
        elif event.button.id == "user-settings":
            self.app.push_screen(UserSettingsScreen(self._runtime))
        elif event.button.id == "close":
            self.dismiss(None)


__all__ = ["SettingsScreen"]
