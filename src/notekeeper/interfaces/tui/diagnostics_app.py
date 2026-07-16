"""Diagnostics modal action for the Textual interface."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from ..contracts import RuntimeDiagnostics
from .common import diagnostics_text


class DiagnosticsScreen(ModalScreen[None]):
    def __init__(self, diagnostics: RuntimeDiagnostics) -> None:
        super().__init__()
        self.diagnostics = diagnostics

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Diagnostics")
            yield Static(diagnostics_text(self.diagnostics), classes="metadata")
            yield Button("Close", id="close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


def open_diagnostics(app) -> None:
    app.push_screen(DiagnosticsScreen(app.runtime.diagnostics(app._selected_campaign_id)))
