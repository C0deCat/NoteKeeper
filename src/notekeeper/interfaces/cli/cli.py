"""Typer application composition."""

from __future__ import annotations

from collections.abc import Callable

import typer

from ..contracts import InterfaceRuntime
from . import (
    campaign_app,
    diagnostics_app,
    job_app,
    participant_app,
    recap_app,
    recording_app,
    recap_prompts_app,
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

    @app.callback()
    def root(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            tui_runner(runtime_factory())

    @app.command("tui")
    def run_tui() -> None:
        tui_runner(runtime_factory())

    cli.add_typer(campaign_app.create_app(runtime_factory), name="campaign")
    cli.add_typer(participant_app.create_app(runtime_factory), name="participant")
    cli.add_typer(sample_app.create_app(runtime_factory), name="sample")
    cli.add_typer(recording_app.create_app(runtime_factory), name="recording")
    cli.add_typer(job_app.create_app(runtime_factory), name="job")
    cli.add_typer(review_app.create_app(runtime_factory), name="review")
    cli.add_typer(transcript_app.create_app(runtime_factory), name="transcript")
    cli.add_typer(recap_app.create_app(runtime_factory), name="recap")
    cli.add_typer(
        recap_prompts_app.create_app(runtime_factory),
        name="recap-prompts",
    )
    diagnostics_app.register_command(cli, runtime_factory)
    app.add_typer(cli, name="cli")
    return app
