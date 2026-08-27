"""Workspace settings form for the Textual interface."""

from textual.app import ComposeResult
from typing import cast

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from notekeeper.application import ApplicationError
from notekeeper.domain import DomainError, WorkspaceRole

from ..contracts import InterfaceRuntime
from .settings_confirmation_screen import SettingsConfirmationScreen
from .workspace_members_screen import WorkspaceMembersScreen
from .modal_header import ModalHeader
from .modal_body import ModalBody


class WorkspaceSettingsScreen(ModalScreen[None]):
    def __init__(self, runtime: InterfaceRuntime) -> None:
        super().__init__()
        self._runtime = runtime
        service = runtime.use_cases.settings
        if service is None:
            raise RuntimeError("settings service is unavailable")
        self._service = service
        self._settings = service.get_workspace()
        self._catalog = service.catalog
        self._owner = service.current_role() is WorkspaceRole.OWNER

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal workspace-settings-form"):
            yield ModalHeader(f"Workspace — {self._settings.name}")
            with ModalBody(classes="modal-body"):
                with Vertical(classes="form-group"):
                    yield Label("Name")
                    yield Input(
                        value=self._settings.name,
                        id="workspace-name",
                        disabled=not self._owner,
                    )
                with Vertical(classes="form-group"):
                    yield Label("WhisperX model")
                    yield Select(
                        ((value, value) for value in self._catalog.whisperx_models),
                        value=self._settings.whisperx_model_name,
                        allow_blank=False,
                        id="workspace-whisperx-model",
                        disabled=not self._owner,
                    )
                with Vertical(classes="form-group"):
                    yield Label("Transcription language")
                    language = self._settings.whisperx_language or "auto"
                    yield Select(
                        (
                            (
                                value.upper() if value != "auto" else "Auto",
                                value,
                            )
                            for value in self._catalog.whisperx_languages
                        ),
                        value=language,
                        allow_blank=False,
                        id="workspace-language",
                        disabled=not self._owner,
                    )
                with Vertical(classes="form-group"):
                    yield Label("Recap model")
                    yield Select(
                        ((value, value) for value in self._catalog.deepseek_models),
                        value=self._settings.deepseek_model_name,
                        allow_blank=False,
                        id="workspace-recap-model",
                        disabled=not self._owner,
                    )
                with Vertical(classes="form-group"):
                    yield Label("Recap temperature")
                    yield Select(
                        (
                            (f"{value:.1f}", value)
                            for value in self._catalog.temperatures
                        ),
                        value=self._settings.deepseek_temperature,
                        allow_blank=False,
                        id="workspace-temperature",
                        disabled=not self._owner,
                    )
                yield Static("", id="workspace-settings-status")
                with Horizontal(classes="modal-actions"):
                    yield Button(
                        "Save",
                        id="save-workspace-settings",
                        variant="primary",
                        disabled=not self._owner,
                    )
                    yield Button(
                        "Reset processing defaults",
                        id="reset-workspace-settings",
                        variant="warning",
                        disabled=not self._owner,
                    )
                    yield Button(
                        "Access",
                        id="workspace-access",
                        disabled=not self._runtime.auth.enabled,
                    )
                    yield Button("Back", id="back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-workspace-settings":
            self._save()
        elif event.button.id == "reset-workspace-settings":
            self.app.push_screen(
                SettingsConfirmationScreen(
                    "Reset workspace processing settings to platform defaults?",
                    "Reset",
                ),
                self._reset_confirmed,
            )
        elif event.button.id == "workspace-access":
            self.app.push_screen(WorkspaceMembersScreen(self._runtime))
        elif event.button.id == "back":
            self.dismiss(None)

    def _save(self) -> None:
        try:
            language = str(self.query_one("#workspace-language", Select).value)
            self._settings = self._service.update_workspace(
                name=self.query_one("#workspace-name", Input).value,
                whisperx_model_name=str(
                    self.query_one("#workspace-whisperx-model", Select).value
                ),
                whisperx_language=None if language == "auto" else language,
                deepseek_model_name=str(
                    self.query_one("#workspace-recap-model", Select).value
                ),
                deepseek_temperature=cast(
                    float,
                    self.query_one("#workspace-temperature", Select).value,
                ),
            )
        except (ApplicationError, DomainError, ValueError) as exc:
            self.query_one("#workspace-settings-status", Static).update(str(exc))
            return
        self.notify("Workspace settings saved")

    def _reset_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            self._settings = self._service.reset_workspace()
        except (ApplicationError, DomainError, ValueError) as exc:
            self.query_one("#workspace-settings-status", Static).update(str(exc))
            return
        self.dismiss(None)


__all__ = ["WorkspaceSettingsScreen"]
