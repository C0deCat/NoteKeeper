"""Multiline campaign recap prompt editor."""

from typing import Literal, cast

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static, TextArea

from notekeeper.application import (
    ApplicationError,
    GetRecapGuidancesCommand,
    UpdateRecapGuidancesCommand,
)
from notekeeper.domain import DomainError

from ..contracts import InterfaceRuntime

PromptKind = Literal["chunk", "combined"]


class RecapPromptEditorScreen(ModalScreen[None]):
    def __init__(
        self,
        runtime: InterfaceRuntime,
        campaign_id: str,
        campaign_name: str,
        prompt_kind: str,
    ) -> None:
        super().__init__()
        if prompt_kind not in {"chunk", "combined"}:
            raise ValueError(f"unknown recap prompt kind: {prompt_kind}")
        self._runtime = runtime
        self._campaign_id = campaign_id
        self._campaign_name = campaign_name
        self._prompt_kind = cast(PromptKind, prompt_kind)

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal recap-prompt-editor"):
            yield Label(f"{self._title()} — {self._campaign_name}")
            yield TextArea(id="recap-prompt-text")
            yield Static("", id="recap-prompt-status")
            with Horizontal():
                yield Button("Save", id="save", variant="primary", disabled=True)
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        try:
            result = self._runtime.use_cases.get_recap_guidances.execute(
                GetRecapGuidancesCommand(campaign_id=self._campaign_id),
            )
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))
            return
        editor = self.query_one("#recap-prompt-text", TextArea)
        editor.text = (
            result.chunk_recap_guidances
            if self._prompt_kind == "chunk"
            else result.combined_recap_guidances
        )
        editor.focus()
        self._update_save_button()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "recap-prompt-text":
            self._update_save_button()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()
        elif event.button.id == "cancel":
            self.dismiss(None)

    def _save(self) -> None:
        guidance = self.query_one("#recap-prompt-text", TextArea).text
        if not guidance.strip():
            self._update_save_button()
            return
        command = UpdateRecapGuidancesCommand(
            campaign_id=self._campaign_id,
            chunk_recap_guidances=(
                guidance if self._prompt_kind == "chunk" else None
            ),
            combined_recap_guidances=(
                guidance if self._prompt_kind == "combined" else None
            ),
        )
        try:
            self._runtime.use_cases.update_recap_guidances.execute(command)
        except (ApplicationError, DomainError, ValueError) as exc:
            self._set_status(str(exc))
            return
        self.dismiss(None)

    def _update_save_button(self) -> None:
        guidance = self.query_one("#recap-prompt-text", TextArea).text
        self.query_one("#save", Button).disabled = not bool(guidance.strip())

    def _title(self) -> str:
        return (
            "Chunk Recap Prompt"
            if self._prompt_kind == "chunk"
            else "Combined Recap Prompt"
        )

    def _set_status(self, message: str) -> None:
        self.query_one("#recap-prompt-status", Static).update(message)


__all__ = ["RecapPromptEditorScreen"]
