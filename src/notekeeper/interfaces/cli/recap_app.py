"""Recap CLI commands."""

import typer

from notekeeper.application import ExportRecapMarkdownCommand, PreviewRecapMarkdownCommand

from .common import RuntimeFactory, run


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Preview and export recaps.")

    @app.command("preview")
    def preview_recap(recap_id: str) -> None:
        runtime = runtime_factory()
        run(
            lambda: typer.echo(
                runtime.use_cases.preview_recap_markdown.execute(
                    PreviewRecapMarkdownCommand(recap_id=recap_id),
                ).markdown,
                nl=False,
            ),
        )

    @app.command("export")
    def export_recap(recap_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.export_recap_markdown.execute(
                ExportRecapMarkdownCommand(recap_id=recap_id),
            )
            typer.echo(runtime.format_artifact_location(result.artifact))

        run(action)

    return app
