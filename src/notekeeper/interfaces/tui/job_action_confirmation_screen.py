"""Confirmation screen for destructive processing-job actions."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class JobActionConfirmationScreen(ModalScreen[bool]):
    def __init__(self, action: str, job_id: str) -> None:
        super().__init__()
        self._action = action
        self._job_id = job_id

    def compose(self) -> ComposeResult:
        if self._action == "delete":
            message = (
                f"Delete job {self._job_id} and its temporary files?"
            )
            detail = "Transcripts and recaps will be preserved. This cannot be undone."
            label = "Delete Job"
        else:
            message = f"Cancel running job {self._job_id}?"
            detail = "The job and every process started by it will be stopped."
            label = "Cancel Job"
        with Vertical(classes="modal"):
            yield Label(message)
            yield Label(detail)
            yield Button(label, id="confirm", variant="error")
            yield Button("Back", id="back", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


__all__ = ["JobActionConfirmationScreen"]
