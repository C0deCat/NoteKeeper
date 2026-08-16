"""Local user registration screen."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from notekeeper.application import ApplicationError
from notekeeper.domain import AuthenticatedUser, DomainError

from ..contracts import InterfaceRuntime


class RegistrationScreen(ModalScreen[AuthenticatedUser | None]):
    def __init__(self, runtime: InterfaceRuntime) -> None:
        super().__init__()
        self._runtime = runtime

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal auth-modal"):
            yield Label("Register")
            yield Input(placeholder="Login", id="register-login")
            yield Input(placeholder="Password", password=True, id="register-password")
            yield Input(
                placeholder="Repeat password",
                password=True,
                id="register-password-confirmation",
            )
            yield Static("", classes="auth-error", id="register-error")
            with Horizontal():
                yield Button("Register", id="register", variant="primary")
                yield Button("Back", id="back")

    def on_mount(self) -> None:
        self.query_one("#register-login", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss(None)
            return
        login = self.query_one("#register-login", Input).value.strip()
        password = self.query_one("#register-password", Input).value
        confirmation = self.query_one("#register-password-confirmation", Input).value
        if password != confirmation:
            self._show_error("Passwords do not match")
            return
        try:
            user = self._runtime.auth.register(login, password)
        except (ApplicationError, DomainError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self.dismiss(user)

    def _show_error(self, message: str) -> None:
        self.query_one("#register-error", Static).update(message)


__all__ = ["RegistrationScreen"]
