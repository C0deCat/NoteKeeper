"""CLI authentication commands."""
# pyright: reportUnusedFunction=false

from __future__ import annotations

import typer

from notekeeper.application import ApplicationError
from notekeeper.infrastructure.auth import LocalCliSessionStore

from .common import RuntimeFactory, run


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Manage the local authentication session.")

    @app.command("login")
    def login(
        login_name: str = typer.Argument(..., metavar="LOGIN"),
        password: str | None = typer.Option(None, "--password", hide_input=True),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            if not runtime.auth.enabled:
                raise ApplicationError("authentication is disabled")
            resolved_password = password or typer.prompt("Password", hide_input=True)
            user = runtime.auth.login(login_name, resolved_password)
            LocalCliSessionStore(runtime.cli_auth_session_path).save(
                login_name.strip(), resolved_password
            )
            typer.echo(f"logged_in login={user.login} user_id={user.id}")

        run(action)

    @app.command("register")
    def register(
        login_name: str = typer.Argument(..., metavar="LOGIN"),
        password: str | None = typer.Option(None, "--password", hide_input=True),
        password_confirmation: str | None = typer.Option(
            None, "--password-confirmation", hide_input=True
        ),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            if not runtime.auth.enabled:
                raise ApplicationError("authentication is disabled")
            resolved_password = password or typer.prompt("Password", hide_input=True)
            confirmation = password_confirmation or typer.prompt(
                "Repeat password", hide_input=True
            )
            if resolved_password != confirmation:
                raise ApplicationError("passwords do not match")
            user = runtime.auth.register(login_name, resolved_password)
            LocalCliSessionStore(runtime.cli_auth_session_path).save(
                login_name.strip(), resolved_password
            )
            typer.echo(f"registered login={user.login} user_id={user.id}")

        run(action)

    @app.command("logout")
    def logout() -> None:
        runtime = runtime_factory()

        def action() -> None:
            LocalCliSessionStore(runtime.cli_auth_session_path).clear()
            runtime.auth.logout()
            typer.echo("logged_out")

        run(action)

    @app.command("status")
    def status() -> None:
        runtime = runtime_factory()

        def action() -> None:
            if not runtime.auth.enabled:
                user = runtime.auth.require_user()
                typer.echo(
                    f"auth_enabled=false login={user.login} user_id={user.id}"
                )
                return
            credentials = LocalCliSessionStore(
                runtime.cli_auth_session_path
            ).load()
            if credentials is None:
                typer.echo("auth_enabled=true authenticated=false")
                return
            user = runtime.auth.login(*credentials)
            typer.echo(
                f"auth_enabled=true authenticated=true login={user.login} user_id={user.id}"
            )

        run(action)

    return app


__all__ = ["create_app"]
