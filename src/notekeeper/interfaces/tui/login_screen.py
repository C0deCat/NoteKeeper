"""Local authentication login screen."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from notekeeper.application import ApplicationError
from notekeeper.domain import AuthenticatedUser, DomainError

from ..contracts import InterfaceRuntime
from .registration_screen import RegistrationScreen


class LoginScreen(ModalScreen[AuthenticatedUser]):
    def __init__(self, runtime: InterfaceRuntime) -> None:
        super().__init__()
        self._runtime = runtime

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal auth-modal"):
            yield Label("Sign in")
            yield Input(placeholder="Login", id="login")
            yield Input(placeholder="Password", password=True, id="password")
            yield Static("", classes="auth-error", id="login-error")
            with Horizontal():
                yield Button("Sign in", id="sign-in", variant="primary")
                yield Button("Register", id="open-registration")

    def on_mount(self) -> None:
        self.query_one("#login", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-registration":
            self.app.push_screen(
                RegistrationScreen(self._runtime),
                self._registration_completed,
            )
            return
        login = self.query_one("#login", Input).value.strip()
        password = self.query_one("#password", Input).value
        try:
            user = self._runtime.auth.login(login, password)
        except (ApplicationError, DomainError, ValueError) as exc:
            self.query_one("#login-error", Static).update(str(exc))
            return
        self.dismiss(user)

    def _registration_completed(self, user: AuthenticatedUser | None) -> None:
        if user is not None:
            self.dismiss(user)


__all__ = ["LoginScreen"]
