import asyncio
from pathlib import Path

from textual.geometry import Region
from textual.widgets import Button, Input, Select, Static
from typer.testing import CliRunner

from notekeeper.composition import NoteKeeperSettings, build_local_host
from notekeeper.interfaces.cli import build_app
from notekeeper.interfaces.tui import LoginScreen, NoteKeeperTui, RegistrationScreen


def _interactive_runtime(settings: NoteKeeperSettings):
    return build_local_host(settings).interactive_runtime()


def _settings(tmp_path: Path, *, auth_enabled: bool = True) -> NoteKeeperSettings:
    return NoteKeeperSettings(
        _env_file=None,
        auth_enabled=auth_enabled,
        local_auth_users_path=tmp_path / "users.json",
        cli_auth_session_path=tmp_path / "session.json",
        storage_root=tmp_path / "artifacts",
        sqlite_path=tmp_path / "notekeeper.sqlite3",
        processing_work_root=tmp_path / "work",
    )


def _assert_icon_button_centered(button: Button, icon: str) -> None:
    assert button.content_region == button.region
    lines = button.render_lines(Region(0, 0, button.size.width, button.size.height))
    center_row = button.size.height // 2
    center_column = button.size.width // 2
    assert lines[center_row].text[center_column] == icon
    assert "".join(line.text for line in lines).strip() == icon


def test_cli_auth_session_controls_existing_working_commands(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    app = build_app(lambda: _interactive_runtime(settings), lambda _runtime: None)
    runner = CliRunner()

    missing = runner.invoke(app, ["cli", "campaign", "list"])
    assert missing.exit_code == 1
    assert "run notekeeper auth login" in missing.output

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
    assert "registered login=alice" in registered.output

    created = runner.invoke(app, ["cli", "campaign", "create", "Alice game"])
    assert created.exit_code == 0
    assert "name=Alice game" in created.output

    status = runner.invoke(app, ["auth", "status"])
    assert status.exit_code == 0
    assert "authenticated=true login=alice" in status.output

    logged_out = runner.invoke(app, ["auth", "logout"])
    assert logged_out.exit_code == 0
    assert not (tmp_path / "session.json").exists()


def test_tui_requires_login_and_registration_logs_user_in(tmp_path: Path) -> None:
    async def run() -> None:
        runtime = _interactive_runtime(_settings(tmp_path))
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, LoginScreen)

            app.screen.query_one("#login", Input).value = "root"
            app.screen.query_one("#password", Input).value = "wrong"
            await pilot.click("#sign-in")
            await pilot.pause()
            assert isinstance(app.screen, LoginScreen)
            assert "invalid login or password" in str(
                app.screen.query_one("#login-error", Static).render()
            )

            await pilot.click("#open-registration")
            await pilot.pause()
            assert isinstance(app.screen, RegistrationScreen)
            app.screen.query_one("#register-login", Input).value = "alice"
            app.screen.query_one("#register-password", Input).value = "secret"
            app.screen.query_one(
                "#register-password-confirmation", Input
            ).value = "different"
            app.screen.query_one("#register", Button).press()
            await pilot.pause()
            assert isinstance(app.screen, RegistrationScreen)
            assert "Passwords do not match" in str(
                app.screen.query_one("#register-error", Static).render()
            )
            app.screen.query_one(
                "#register-password-confirmation", Input
            ).value = "secret"
            app.screen.query_one("#register", Button).press()
            await pilot.pause()

            assert not isinstance(app.screen, (LoginScreen, RegistrationScreen))
            assert runtime.auth.current_user is not None
            assert runtime.auth.current_user.login == "alice"
            logout = app.query_one("#logout", Button)
            settings_button = app.query_one("#settings", Button)
            user = app.query_one("#auth-user", Static)
            job_count = app.query_one("#job-count", Static)
            account_status = app.query_one("#account-status")
            topbar = app.query_one("#topbar")
            workspace_select = app.query_one("#workspace-select", Select)
            campaign_select = app.query_one("#campaign-select", Select)
            assert str(logout.label) == "⇥"
            assert logout.variant == "error"
            assert logout.tooltip == "Logout"
            assert logout.region.x < user.region.x
            assert job_count.region.x == user.region.x
            assert job_count.region.y < user.region.y
            assert account_status.region.right == topbar.content_region.right
            assert workspace_select.region.width >= 24
            assert campaign_select.region.width >= 24
            assert str(settings_button.label) == "⚙"
            assert settings_button.tooltip == "Settings"
            _assert_icon_button_centered(settings_button, "⚙")
            _assert_icon_button_centered(logout, "⇥")
            assert str(app.query_one("#manage-campaign", Button).label) == "Campaigns"
            assert len(app.query("#status")) == 0

            await pilot.click("#logout")
            await pilot.pause()
            assert isinstance(app.screen, LoginScreen)
            assert runtime.auth.current_user is None

    asyncio.run(run())


def test_tui_skips_authentication_when_disabled(tmp_path: Path) -> None:
    async def run() -> None:
        runtime = _interactive_runtime(_settings(tmp_path, auth_enabled=False))
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not isinstance(app.screen, LoginScreen)
            assert len(app.query("#logout")) == 0
            assert runtime.auth.current_user is not None
            assert runtime.auth.current_user.login == "root"

    asyncio.run(run())
