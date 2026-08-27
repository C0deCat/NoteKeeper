"""Markdown preview modal screen."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown

from .modal_header import ModalHeader


class MarkdownPreviewScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("end", "scroll_to_end", "End", show=False, priority=True),
    ]

    def __init__(self, title: str, markdown: str) -> None:
        super().__init__()
        self._preview_title = title
        self._markdown = markdown

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal large-modal preview-modal"):
            yield ModalHeader(self._preview_title, close=True)
            with VerticalScroll(classes="modal-body", id="preview-scroll"):
                yield Markdown(self._markdown, id="preview-markdown")

    def on_mount(self) -> None:
        self.query_one("#preview-scroll", VerticalScroll).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_scroll_to_end(self) -> None:
        self.query_one("#preview-scroll", VerticalScroll).scroll_end(
            animate=False,
            immediate=True,
        )
