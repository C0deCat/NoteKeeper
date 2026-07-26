"""Confirmation screen for destructive recording and player actions."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ObjectActionConfirmationScreen(ModalScreen[bool]):
    """Confirm removal of a recording or player."""

    def __init__(self, object_kind: str, object_name: str) -> None:
        super().__init__()
        self._object_kind = object_kind
        self._object_name = object_name

    def compose(self) -> ComposeResult:
        if self._object_kind == "recording":
            message = f"Remove recording {self._object_name}?"
            detail = (
                "Pending jobs will also be removed. The source audio file will be "
                "preserved."
            )
            label = "Remove Recording"
        else:
            message = f"Remove player {self._object_name}?"
            detail = "All voice samples for this player will also be removed."
            label = "Remove Player"
        with Vertical(classes="modal"):
            yield Label(message)
            yield Label(detail)
            yield Button(label, id="confirm", variant="error")
            yield Button("Back", id="back", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


__all__ = ["ObjectActionConfirmationScreen"]
