import asyncio
import json
from pathlib import Path

from textual.widgets import Button, Input, Label, Select, Static
from typer.testing import CliRunner

from notekeeper.composition import NoteKeeperSettings, build_local_host
from notekeeper.domain import WorkspaceRole
from notekeeper.interfaces.cli import build_app
from notekeeper.interfaces.tui.settings_screen import SettingsScreen
from notekeeper.interfaces.tui.tui import NoteKeeperTui
from notekeeper.interfaces.tui.user_settings_screen import UserSettingsScreen
from notekeeper.interfaces.tui.workspace_settings_screen import (
    WorkspaceSettingsScreen,
)


def _settings(tmp_path: Path, *, auth_enabled: bool = False) -> NoteKeeperSettings:
    return NoteKeeperSettings(
        _env_file=None,
        auth_enabled=auth_enabled,
        local_auth_users_path=tmp_path / "users.json",
        cli_auth_session_path=tmp_path / "session.json",
        storage_root=tmp_path / "artifacts",
        sqlite_path=tmp_path / "notekeeper.sqlite3",
        processing_work_root=tmp_path / "work",
        recap_prompts_template_path=Path("data") / "recap_prompts.json",
    )


def _assert_modal_sections_fill_surface(screen) -> None:
    modal = screen.query_one(".modal")
    header = screen.query_one(".modal-header")
    body = screen.query_one(".modal-body")

    assert not modal.styles.border
    assert not modal.styles.outline
    assert modal.styles.background.a == 0
    assert body.styles.background.a > 0
    assert header.region.x == modal.region.x
    assert header.region.y == modal.region.y
    assert header.region.width == modal.region.width
    assert body.region.x == modal.region.x
    assert body.region.y == header.region.bottom
    assert body.region.width == modal.region.width
    assert body.region.bottom == modal.region.bottom


def test_cli_workspace_settings_show_set_and_reset(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    app = build_app(
        lambda: build_local_host(settings).interactive_runtime(),
        lambda _runtime: None,
    )
    runner = CliRunner()

    shown = runner.invoke(app, ["cli", "settings", "workspace", "show"])
    assert shown.exit_code == 0
    assert json.loads(shown.output)["whisperx_model_name"] == "large-v3-turbo"

    updated = runner.invoke(
        app,
        [
            "cli",
            "settings",
            "workspace",
            "set",
            "--name",
            "Shared",
            "--whisperx-model",
            "small",
            "--language",
            "ru",
            "--recap-model",
            "deepseek-v4-flash",
            "--temperature",
            "1.3",
        ],
    )
    assert updated.exit_code == 0
    payload = json.loads(updated.output)
    assert payload["name"] == "Shared"
    assert payload["whisperx_language"] == "ru"

    reset = runner.invoke(
        app,
        ["cli", "settings", "workspace", "reset", "--yes"],
    )
    assert reset.exit_code == 0
    assert json.loads(reset.output)["inherited"] is True


def test_cli_user_login_and_password_update_session(tmp_path: Path) -> None:
    settings = _settings(tmp_path, auth_enabled=True)
    app = build_app(
        lambda: build_local_host(settings).interactive_runtime(),
        lambda _runtime: None,
    )
    runner = CliRunner()
    registered = runner.invoke(
        app,
        [
            "auth",
            "register",
            "alice",
            "--password",
            "secret",
            "--password-confirmation",
            "secret",
        ],
    )
    assert registered.exit_code == 0

    renamed = runner.invoke(
        app,
        [
            "cli",
            "settings",
            "user",
            "login",
            "alice-new",
            "--current-password",
            "secret",
        ],
    )
    assert renamed.exit_code == 0
    assert json.loads(renamed.output)["login"] == "alice-new"

    password = runner.invoke(
        app,
        [
            "cli",
            "settings",
            "user",
            "password",
            "--current-password",
            "secret",
            "--new-password",
            "new-secret",
            "--new-password-confirmation",
            "new-secret",
        ],
    )
    assert password.exit_code == 0
    status = runner.invoke(app, ["auth", "status"])
    assert status.exit_code == 0
    assert "login=alice-new" in status.output


def test_cli_workspace_option_selects_an_accessible_workspace(tmp_path: Path) -> None:
    settings = _settings(tmp_path, auth_enabled=True)
    host = build_local_host(settings)
    alice = host.interactive_runtime()
    alice.auth.register("alice", "secret")
    alice_service = alice.use_cases.settings
    assert alice_service is not None
    alice_workspace = alice_service.get_workspace()
    alice_service.add_member("root", WorkspaceRole.EDITOR)

    app = build_app(
        lambda: build_local_host(settings).interactive_runtime(),
        lambda _runtime: None,
    )
    runner = CliRunner()
    logged_in = runner.invoke(
        app,
        ["auth", "login", "root", "--password", "root"],
    )
    assert logged_in.exit_code == 0

    shown = runner.invoke(
        app,
        [
            "cli",
            "--workspace",
            str(alice_workspace.workspace_id),
            "settings",
            "workspace",
            "show",
        ],
    )

    assert shown.exit_code == 0
    assert json.loads(shown.output)["workspace_id"] == str(
        alice_workspace.workspace_id
    )


def test_tui_settings_have_category_menu_and_typed_workspace_controls(
    tmp_path: Path,
) -> None:
    async def run_test() -> None:
        runtime = build_local_host(_settings(tmp_path)).interactive_runtime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#settings", Button).disabled is False
            await pilot.click("#settings")
            await pilot.pause()
            assert isinstance(app.screen, SettingsScreen)
            assert app.screen.query_one("#workspace-settings", Button)
            assert app.screen.query_one("#campaign-settings", Button)
            assert app.screen.query_one("#user-settings", Button)
            _assert_modal_sections_fill_surface(app.screen)
            modal = app.screen.query_one(".modal")
            header = app.screen.query_one(".modal-header")
            close = app.screen.query_one("#close", Button)
            assert header.region.x == modal.region.x
            assert header.region.y == modal.region.y
            assert header.region.width == modal.region.width
            assert close.region.right == modal.region.right
            assert close.content_region == close.region
            assert str(close.label) == "×"

            await pilot.click("#workspace-settings")
            await pilot.pause()
            assert isinstance(app.screen, WorkspaceSettingsScreen)
            _assert_modal_sections_fill_surface(app.screen)
            assert app.screen.query_one("#workspace-name", Input)
            assert app.screen.query_one("#workspace-whisperx-model", Select)
            assert app.screen.query_one("#workspace-language", Select)
            assert app.screen.query_one("#workspace-recap-model", Select)
            assert app.screen.query_one("#workspace-temperature", Select)
            form_groups = tuple(app.screen.query(".form-group"))
            assert len(form_groups) == 5
            assert all(group.styles.margin.bottom == 1 for group in form_groups)
            assert app.screen.query_one(".modal-header").region.height == 3

    asyncio.run(run_test())


def test_tui_user_settings_use_group_and_action_spacing(tmp_path: Path) -> None:
    async def run_test() -> None:
        runtime = build_local_host(
            _settings(tmp_path, auth_enabled=True),
        ).interactive_runtime()
        runtime.auth.login("root", "root")
        app = NoteKeeperTui(runtime)

        async with app.run_test(size=(100, 48)) as pilot:
            await pilot.pause()
            screen = UserSettingsScreen(runtime)
            app.push_screen(screen)
            await pilot.pause()
            _assert_modal_sections_fill_surface(screen)

            login = screen.query_one("#user-login", Input)
            current_password = screen.query_one("#user-current-password", Input)
            change_login = screen.query_one("#change-login", Button)
            new_password = screen.query_one("#user-new-password", Input)
            confirmation = screen.query_one(
                "#user-new-password-confirmation",
                Input,
            )
            change_password = screen.query_one("#change-password", Button)
            default_workspace = screen.query_one("#default-workspace", Select)
            save_workspace = screen.query_one("#save-default-workspace", Button)
            status = screen.query_one("#user-settings-status", Static)

            controls = (login, current_password, new_password, confirmation)
            for control in controls:
                label = control.parent.query_one(Label)
                assert label.region.bottom == control.region.y

            current_label = current_password.parent.query_one(Label)
            new_label = new_password.parent.query_one(Label)
            confirmation_label = confirmation.parent.query_one(Label)
            default_label = default_workspace.parent.query_one(Label)
            assert current_label.region.y - login.region.bottom == 1
            assert new_label.region.y - change_login.region.bottom == 2
            assert confirmation_label.region.y - new_password.region.bottom == 1
            assert default_label.region.y - change_password.region.bottom == 2
            assert status.region.y - save_workspace.region.bottom == 2
            assert change_login.styles.margin.bottom == 2
            assert change_password.styles.margin.bottom == 2
            assert save_workspace.styles.margin.bottom == 2

    asyncio.run(run_test())
