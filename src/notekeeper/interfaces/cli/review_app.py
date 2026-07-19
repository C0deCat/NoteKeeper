"""Speaker mapping review CLI commands."""

import typer

from notekeeper.application import ReviewSpeakerMappingsCommand

from .common import (
    RuntimeFactory,
    echo_job,
    parse_keep_mapping,
    parse_label_mapping,
    parse_mapping,
    run,
)


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Review speaker mappings.")

    @app.command("submit")
    def submit_review(
        job_id: str,
        mapping: list[str] | None = typer.Option(
            None,
            "--mapping",
            "-m",
            help="Manual mapping in SPEAKER_00=participant-id form.",
        ),
        label: list[str] | None = typer.Option(
            None,
            "--label",
            "-l",
            help="Standalone label in SPEAKER_00=Guest form.",
        ),
        keep: list[str] | None = typer.Option(
            None,
            "--keep",
            "-k",
            help="Keep a technical speaker label and mark it reviewed.",
        ),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            mappings = (
                *(parse_mapping(item) for item in mapping or ()),
                *(parse_label_mapping(item) for item in label or ()),
                *(parse_keep_mapping(item) for item in keep or ()),
            )
            if not mappings:
                raise ValueError(
                    "at least one --mapping, --label, or --keep is required",
                )
            result = runtime.use_cases.review_speaker_mappings.execute(
                ReviewSpeakerMappingsCommand(
                    job_id=job_id,
                    mappings=mappings,
                ),
            )
            echo_job(result.job)
            for warning in result.warnings:
                typer.echo(f"warning {warning.kind.value}: {warning.message}")

        run(action)

    return app
