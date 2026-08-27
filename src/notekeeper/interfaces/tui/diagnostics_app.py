"""Diagnostics modal action for the Textual interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ..contracts import RuntimeDiagnostics
from .common import diagnostics_text
from .modal_body import ModalBody
from .modal_header import ModalHeader

if TYPE_CHECKING:
    from .tui import NoteKeeperTui


class DiagnosticsScreen(ModalScreen[None]):
    def __init__(self, diagnostics: RuntimeDiagnostics) -> None:
        super().__init__()
        self.diagnostics = diagnostics

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield ModalHeader("Diagnostics", close=True)
            with ModalBody(classes="modal-body"):
                yield Static(diagnostics_text(self.diagnostics), classes="metadata")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


def open_diagnostics(app: NoteKeeperTui) -> None:
    app.push_screen(
        DiagnosticsScreen(app.runtime.diagnostics(app._selected_campaign_id))
    )
