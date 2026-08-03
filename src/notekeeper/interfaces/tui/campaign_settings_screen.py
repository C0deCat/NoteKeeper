"""Campaign-specific settings menu for the Textual interface."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from ..contracts import InterfaceRuntime
from .recap_prompt_editor_screen import RecapPromptEditorScreen


class CampaignSettingsScreen(ModalScreen[None]):
    def __init__(
        self,
        runtime: InterfaceRuntime,
        campaign_id: str,
        campaign_name: str,
    ) -> None:
        super().__init__()
        self._runtime = runtime
        self._campaign_id = campaign_id
        self._campaign_name = campaign_name

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal settings-menu"):
            yield Label(f"Settings — {self._campaign_name}")
            yield Button("Chunk Recap Prompt", id="chunk-recap-prompt")
            yield Button("Combined Recap Prompt", id="combined-recap-prompt")
            yield Button("Close", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "chunk-recap-prompt":
            self._open_editor("chunk")
        elif event.button.id == "combined-recap-prompt":
            self._open_editor("combined")
        elif event.button.id == "close":
            self.dismiss(None)

    def _open_editor(self, prompt_kind: str) -> None:
        self.app.push_screen(
            RecapPromptEditorScreen(
                self._runtime,
                self._campaign_id,
                self._campaign_name,
                prompt_kind,
            ),
        )


__all__ = ["CampaignSettingsScreen"]
