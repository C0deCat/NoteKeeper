"""Shared title sector for NoteKeeper modal screens."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Label


class ModalHeader(Horizontal):
    def __init__(self, title: str, *, close: bool = False) -> None:
        super().__init__(classes="modal-header")
        self._title = title
        self._close = close

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="modal-title")
        if self._close:
            yield Button(
                "×",
                id="close",
                variant="error",
                tooltip="Close",
                classes="modal-close icon-button",
                compact=True,
            )


__all__ = ["ModalHeader"]
