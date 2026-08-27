"""Confirmation modal for settings resets and access removal."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from .modal_body import ModalBody
from .modal_header import ModalHeader


class SettingsConfirmationScreen(ModalScreen[bool]):
    def __init__(self, message: str, action_label: str) -> None:
        super().__init__()
        self._message = message
        self._action_label = action_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield ModalHeader("Confirm Action")
            with ModalBody(classes="modal-body"):
                yield Label(self._message)
                yield Button(self._action_label, id="confirm", variant="error")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


__all__ = ["SettingsConfirmationScreen"]
