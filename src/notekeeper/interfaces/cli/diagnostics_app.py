"""Diagnostics CLI command registration."""

import typer

from .common import RuntimeFactory


def register_command(app: typer.Typer, runtime_factory: RuntimeFactory) -> None:
    @app.command("diagnostics")
    def diagnostics(campaign_id: str | None = None) -> None:
        runtime = runtime_factory()
        snapshot = runtime.diagnostics(campaign_id)
        typer.echo(f"storage_root={snapshot.storage_root}")
        typer.echo(f"sqlite_path={snapshot.sqlite_path}")
        typer.echo(f"processing_work_root={snapshot.processing_work_root}")
        typer.echo(f"recap_prompts_file={snapshot.recap_prompts_file}")
        typer.echo(f"whisperx_model={snapshot.whisperx_model_name}")
        typer.echo(f"whisperx_device={snapshot.whisperx_device}")
        typer.echo(f"whisperx_compute_type={snapshot.whisperx_compute_type}")
        typer.echo(f"whisperx_vad_method={snapshot.whisperx_vad_method}")
        typer.echo(f"deepseek_configured={snapshot.deepseek_configured}")
        typer.echo(f"huggingface_configured={snapshot.huggingface_configured}")
        for message in snapshot.recent_messages:
            typer.echo(f"recent={message}")
