"""Current-user settings screen."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from notekeeper.application import ApplicationError
from notekeeper.domain import DomainError

from ..contracts import InterfaceRuntime
from .modal_header import ModalHeader
from .modal_body import ModalBody


class UserSettingsScreen(ModalScreen[None]):
    def __init__(self, runtime: InterfaceRuntime) -> None:
        super().__init__()
        self._runtime = runtime
        service = runtime.use_cases.settings
        if service is None:
            raise RuntimeError("settings service is unavailable")
        self._service = service
        self._auth_enabled = runtime.auth.enabled
        self._user_settings = service.get_user() if self._auth_enabled else None

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal user-settings-form"):
            yield ModalHeader("User Settings")
            with ModalBody(classes="modal-body"):
                if not self._auth_enabled or self._user_settings is None:
                    yield Static("Authentication is disabled")
                    yield Button("Back", id="back")
                    return
                with Vertical(classes="form-group"):
                    yield Label("Login")
                    yield Input(value=self._user_settings.login, id="user-login")
                with Vertical(classes="form-group"):
                    yield Label("Current password")
                    yield Input(password=True, id="user-current-password")
                yield Button(
                    "Change login",
                    id="change-login",
                    classes="form-action",
                )
                with Vertical(classes="form-group"):
                    yield Label("New password")
                    yield Input(password=True, id="user-new-password")
                with Vertical(classes="form-group"):
                    yield Label("Repeat new password")
                    yield Input(password=True, id="user-new-password-confirmation")
                yield Button(
                    "Change password",
                    id="change-password",
                    classes="form-action",
                )
                with Vertical(classes="form-group"):
                    yield Label("Default workspace")
                    workspaces = self._runtime.list_workspaces()
                    default_value = (
                        str(self._user_settings.default_workspace_id)
                        if self._user_settings.default_workspace_id is not None
                        else str(workspaces[0].id)
                    )
                    yield Select(
                        (
                            (workspace.name, str(workspace.id))
                            for workspace in workspaces
                        ),
                        value=default_value,
                        allow_blank=False,
                        id="default-workspace",
                    )
                yield Button(
                    "Save default workspace",
                    id="save-default-workspace",
                    classes="form-action",
                )
                yield Static("", id="user-settings-status")
                with Horizontal(classes="modal-actions"):
                    yield Button("Back", id="back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "change-login":
            self._change_login()
        elif event.button.id == "change-password":
            self._change_password()
        elif event.button.id == "save-default-workspace":
            self._save_default_workspace()
        elif event.button.id == "back":
            self.dismiss(None)

    def _change_login(self) -> None:
        try:
            user = self._runtime.auth.update_login(
                self.query_one("#user-current-password", Input).value,
                self.query_one("#user-login", Input).value,
            )
        except (ApplicationError, DomainError, ValueError) as exc:
            self._status(str(exc))
            return
        self._status(f"Login changed to {user.login}")

    def _change_password(self) -> None:
        new_password = self.query_one("#user-new-password", Input).value
        confirmation = self.query_one(
            "#user-new-password-confirmation", Input
        ).value
        if new_password != confirmation:
            self._status("Passwords do not match")
            return
        try:
            self._runtime.auth.update_password(
                self.query_one("#user-current-password", Input).value,
                new_password,
            )
        except (ApplicationError, DomainError, ValueError) as exc:
            self._status(str(exc))
            return
        self._status("Password changed")

    def _save_default_workspace(self) -> None:
        try:
            value = str(self.query_one("#default-workspace", Select).value)
            self._service.update_default_workspace(value)
        except (ApplicationError, DomainError, ValueError) as exc:
            self._status(str(exc))
            return
        self._status("Default workspace saved")

    def _status(self, message: str) -> None:
        self.query_one("#user-settings-status", Static).update(message)


__all__ = ["UserSettingsScreen"]
