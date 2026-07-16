"""Speaker mapping review CLI commands."""

import typer

from notekeeper.application import ReviewSpeakerMappingsCommand

from .common import RuntimeFactory, echo_job, parse_mapping, run


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Review speaker mappings.")

    @app.command("submit")
    def submit_review(
        job_id: str,
        mapping: list[str] = typer.Option(
            ...,
            "--mapping",
            "-m",
            help="Manual mapping in SPEAKER_00=participant-id form.",
        ),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.review_speaker_mappings.execute(
                ReviewSpeakerMappingsCommand(
                    job_id=job_id,
                    mappings=tuple(parse_mapping(item) for item in mapping),
                ),
            )
            echo_job(result.job)
            for warning in result.warnings:
                typer.echo(f"warning {warning.kind.value}: {warning.message}")

        run(action)

    return app
