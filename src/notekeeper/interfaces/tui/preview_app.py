"""Markdown preview modal screen."""

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Markdown


class MarkdownPreviewScreen(ModalScreen[None]):
    def __init__(self, title: str, markdown: str) -> None:
        super().__init__()
        self.title = title
        self.markdown = markdown

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label(self.title)
            with VerticalScroll(id="preview-scroll"):
                yield Markdown(self.markdown, id="preview-markdown")
            yield Button("Close", id="close", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#preview-scroll", VerticalScroll).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)
