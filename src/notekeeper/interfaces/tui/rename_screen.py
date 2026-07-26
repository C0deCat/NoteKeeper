"""Modal screen for renaming dashboard objects."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class RenameScreen(ModalScreen[str | None]):
    """Collect a non-empty replacement name."""

    def __init__(self, title: str, current_name: str) -> None:
        super().__init__()
        self._title = title
        self._current_name = current_name

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label(self._title)
            yield Input(value=self._current_name, id="new-name")
            yield Button("Rename", id="rename", variant="primary")
            yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        name_input = self.query_one("#new-name", Input)
        name_input.focus()
        name_input.action_end()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "new-name":
            self.query_one("#rename", Button).disabled = not event.value.strip()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rename":
            name = self.query_one("#new-name", Input).value.strip()
            if name:
                self.dismiss(name)
        else:
            self.dismiss(None)


__all__ = ["RenameScreen"]
