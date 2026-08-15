"""Typer application composition."""
# Typer registers nested command callbacks.
# pyright: reportUnusedFunction=false

from __future__ import annotations

from collections.abc import Callable

import typer

from notekeeper.application import ApplicationError
from notekeeper.infrastructure.auth import LocalCliSessionStore

from ..contracts import InterfaceRuntime
from . import (
    auth_app,
    campaign_app,
    diagnostics_app,
    job_app,
    participant_app,
    recap_app,
    recap_prompts_app,
    recording_app,
    review_app,
    sample_app,
    transcript_app,
)
from .common import RuntimeFactory

TuiRunner = Callable[[InterfaceRuntime], None]


def build_app(
    runtime_factory: RuntimeFactory,
    tui_runner: TuiRunner,
) -> typer.Typer:
    app = typer.Typer(
        invoke_without_command=True,
        no_args_is_help=False,
        help="NoteKeeper application.",
    )
    cli = typer.Typer(help="Scriptable Stage 1 commands.")

    def authenticated_runtime_factory() -> InterfaceRuntime:
        runtime = runtime_factory()
        auth = getattr(runtime, "auth", None)
        if auth is None or not auth.enabled:
            return runtime
        try:
            credentials = LocalCliSessionStore(runtime.cli_auth_session_path).load()
            if credentials is None:
                raise ApplicationError(
                    "authentication required; run notekeeper auth login"
                )
            auth.login(*credentials)
        except (ApplicationError, ValueError) as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        return runtime

    @app.callback()
    def root(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            tui_runner(runtime_factory())

    @app.command("tui")
    def run_tui() -> None:
        tui_runner(runtime_factory())

    cli.add_typer(campaign_app.create_app(authenticated_runtime_factory), name="campaign")
    cli.add_typer(participant_app.create_app(authenticated_runtime_factory), name="participant")
    cli.add_typer(sample_app.create_app(authenticated_runtime_factory), name="sample")
    cli.add_typer(recording_app.create_app(authenticated_runtime_factory), name="recording")
    cli.add_typer(job_app.create_app(authenticated_runtime_factory), name="job")
    cli.add_typer(review_app.create_app(authenticated_runtime_factory), name="review")
    cli.add_typer(transcript_app.create_app(authenticated_runtime_factory), name="transcript")
    cli.add_typer(recap_app.create_app(authenticated_runtime_factory), name="recap")
    cli.add_typer(
        recap_prompts_app.create_app(authenticated_runtime_factory),
        name="recap-prompts",
    )
    diagnostics_app.register_command(cli, authenticated_runtime_factory)
    app.add_typer(cli, name="cli")
    app.add_typer(auth_app.create_app(runtime_factory), name="auth")
    return app
