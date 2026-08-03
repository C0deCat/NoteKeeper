"""Campaign recap prompt CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from notekeeper.application import (
    GetRecapGuidancesCommand,
    UpdateRecapGuidancesCommand,
)

from .common import RuntimeFactory, run


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Show and update campaign recap prompts.")

    @app.command("show")
    def show_recap_prompts(campaign_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.get_recap_guidances.execute(
                GetRecapGuidancesCommand(campaign_id=campaign_id),
            )
            _echo_guidances(
                result.chunk_recap_guidances,
                result.combined_recap_guidances,
            )

        run(action)

    @app.command("set")
    def set_recap_prompts(
        campaign_id: str,
        chunk_file: Path = typer.Option(..., "--chunk-file"),
        combined_file: Path = typer.Option(..., "--combined-file"),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.update_recap_guidances.execute(
                UpdateRecapGuidancesCommand(
                    campaign_id=campaign_id,
                    chunk_recap_guidances=_read_prompt_file(chunk_file),
                    combined_recap_guidances=_read_prompt_file(combined_file),
                ),
            )
            _echo_guidances(
                result.chunk_recap_guidances,
                result.combined_recap_guidances,
            )

        run(action)

    return app


def _read_prompt_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"could not read prompt file: {path}") from exc


def _echo_guidances(chunk_guidance: str, combined_guidance: str) -> None:
    typer.echo(
        json.dumps(
            {
                "chunk_recap_prompt": chunk_guidance,
                "combine_chunks_prompt": combined_guidance,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )


__all__ = ["create_app"]
