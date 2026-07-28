"""Shared audio file explorer for the Textual interface."""

from pathlib import Path

from textual_fspicker import FileOpen


class AudioFileExplorerScreen(FileOpen):
    def __init__(self, location: str | Path | None = None) -> None:
        initial_location = Path(location or "data").expanduser().resolve(strict=False)
        self.initial_location = initial_location
        super().__init__(
            location=initial_location,
            title="Select Audio File",
            open_button="Select",
            cancel_button="Cancel",
            must_exist=True,
            suggest_completions=True,
        )
