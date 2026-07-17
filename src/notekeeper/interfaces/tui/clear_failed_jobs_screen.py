"""Confirmation screen for clearing failed processing jobs."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ClearFailedJobsScreen(ModalScreen[bool]):
    def __init__(self, failed_job_count: int) -> None:
        super().__init__()
        self._failed_job_count = failed_job_count

    def compose(self) -> ComposeResult:
        noun = "job" if self._failed_job_count == 1 else "jobs"
        with Vertical(classes="modal"):
            yield Label(
                f"Clear {self._failed_job_count} failed {noun} and related files?",
            )
            yield Label("This action cannot be undone.")
            yield Button("Clear Failed Jobs", id="confirm-clear", variant="error")
            yield Button("Cancel", id="cancel", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-clear")
