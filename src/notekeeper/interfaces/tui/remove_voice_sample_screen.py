"""Voice-sample selection and removal confirmation screen."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select

from notekeeper.domain import VoiceSample


class RemoveVoiceSampleScreen(ModalScreen[str | None]):
    """Select one of a player's samples and confirm its removal."""

    def __init__(self, samples: tuple[VoiceSample, ...]) -> None:
        super().__init__()
        self._samples = samples

    def compose(self) -> ComposeResult:
        options = tuple(
            (f"{sample.id} — {sample.artifact.uri}", str(sample.id))
            for sample in self._samples
        )
        with Vertical(classes="modal"):
            yield Label("Remove Voice Sample")
            yield Select(options, prompt="Voice sample", id="voice-sample")
            yield Label("The source audio file will be preserved.")
            yield Button(
                "Remove Voice Sample",
                id="remove",
                variant="error",
                disabled=True,
            )
            yield Button("Back", id="back", variant="primary")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "voice-sample":
            self.query_one("#remove", Button).disabled = event.value in (
                Select.BLANK,
                Select.NULL,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "remove":
            self.dismiss(None)
            return
        sample_id = self.query_one("#voice-sample", Select).value
        if sample_id not in (Select.BLANK, Select.NULL):
            self.dismiss(str(sample_id))


__all__ = ["RemoveVoiceSampleScreen"]
