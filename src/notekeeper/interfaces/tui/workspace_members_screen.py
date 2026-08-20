"""Workspace membership management screen."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from notekeeper.application import ApplicationError
from notekeeper.domain import DomainError, WorkspaceRole

from ..contracts import InterfaceRuntime
from .settings_confirmation_screen import SettingsConfirmationScreen


class WorkspaceMembersScreen(ModalScreen[None]):
    def __init__(self, runtime: InterfaceRuntime) -> None:
        super().__init__()
        service = runtime.use_cases.settings
        if service is None:
            raise RuntimeError("settings service is unavailable")
        self._runtime = runtime
        self._service = service
        self._selected_login: str | None = None
        self._owner = service.current_role() is WorkspaceRole.OWNER

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal workspace-members"):
            yield Label("Workspace access")
            yield DataTable(id="workspace-members-table")
            with Horizontal():
                yield Input(
                    placeholder="Existing user login",
                    id="member-login",
                    disabled=not self._owner,
                )
                yield Select(
                    (("Editor", "editor"), ("Viewer", "viewer")),
                    value="editor",
                    allow_blank=False,
                    id="member-role",
                    disabled=not self._owner,
                )
            with Horizontal():
                yield Button("Add", id="add-member", disabled=not self._owner)
                yield Button(
                    "Change role", id="change-member-role", disabled=not self._owner
                )
                yield Button(
                    "Remove", id="remove-member", variant="error",
                    disabled=not self._owner,
                )
                yield Button("Back", id="back")
            yield Static("", id="member-status")

    def on_mount(self) -> None:
        table = self.query_one("#workspace-members-table", DataTable)
        table.add_columns("Login", "Role", "User ID")
        self._refresh_members()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = event.data_table.get_row(event.row_key)
        self._selected_login = str(row[0])
        self.query_one("#member-login", Input).value = self._selected_login
        if str(row[1]) in {"editor", "viewer"}:
            self.query_one("#member-role", Select).value = str(row[1])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-member":
            self._mutate("add")
        elif event.button.id == "change-member-role":
            self._mutate("role")
        elif event.button.id == "remove-member":
            login = self._login()
            if login:
                self.app.push_screen(
                    SettingsConfirmationScreen(
                        f"Remove {login!r} from this workspace?", "Remove"
                    ),
                    lambda confirmed: self._remove(login) if confirmed else None,
                )
        elif event.button.id == "back":
            self.dismiss(None)

    def _mutate(self, operation: str) -> None:
        login = self._login()
        if not login:
            return
        role = WorkspaceRole(str(self.query_one("#member-role", Select).value))
        try:
            if operation == "add":
                self._service.add_member(login, role)
            else:
                self._service.update_member_role(login, role)
        except (ApplicationError, DomainError, ValueError) as exc:
            self._status(str(exc))
            return
        self._refresh_members()
        self._status("Saved")

    def _remove(self, login: str) -> None:
        try:
            self._service.remove_member(login)
        except (ApplicationError, DomainError, ValueError) as exc:
            self._status(str(exc))
            return
        self._refresh_members()
        self._status("Removed")

    def _login(self) -> str:
        login = self.query_one("#member-login", Input).value.strip()
        if not login:
            self._status("Enter or select a user login")
        return login

    def _refresh_members(self) -> None:
        table = self.query_one("#workspace-members-table", DataTable)
        table.clear()
        for member in self._service.list_members():
            table.add_row(member.login, member.role.value, str(member.user_id))

    def _status(self, message: str) -> None:
        self.query_one("#member-status", Static).update(message)


__all__ = ["WorkspaceMembersScreen"]
