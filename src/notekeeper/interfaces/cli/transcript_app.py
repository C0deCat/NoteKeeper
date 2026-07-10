"""Transcript CLI commands."""

import typer

from notekeeper.application import (
    ExportTranscriptMarkdownCommand,
    PreviewTranscriptMarkdownCommand,
)

from .common import RuntimeFactory, run


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Preview and export transcripts.")

    @app.command("preview")
    def preview_transcript(transcript_id: str) -> None:
        runtime = runtime_factory()
        run(
            lambda: typer.echo(
                runtime.use_cases.preview_transcript_markdown.execute(
                    PreviewTranscriptMarkdownCommand(transcript_id=transcript_id),
                ).markdown,
                nl=False,
            ),
        )

    @app.command("export")
    def export_transcript(transcript_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.export_transcript_markdown.execute(
                ExportTranscriptMarkdownCommand(transcript_id=transcript_id),
            )
            typer.echo(runtime.format_artifact_location(result.artifact))

        run(action)

    return app
