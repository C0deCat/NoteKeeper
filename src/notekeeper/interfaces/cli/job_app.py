"""Processing job CLI commands."""

import typer

from notekeeper.application import (
    CreateProcessingJobForAudioTrackCommand,
    GenerateRecapCommand,
    GetJobStatusCommand,
    ListJobsForCampaignCommand,
    RestartFailedProcessingJobCommand,
    RunProcessingJobCommand,
)

from .common import RuntimeFactory, echo_audio_track, echo_job, run


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Inspect and run processing jobs.")

    @app.command("list")
    def list_jobs(campaign_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.list_jobs_for_campaign.execute(
                ListJobsForCampaignCommand(campaign_id=campaign_id),
            )
            for job in result.jobs:
                echo_job(job)

        run(action)

    @app.command("create")
    def create_job(audio_track_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.create_processing_job_for_audio_track.execute(
                CreateProcessingJobForAudioTrackCommand(
                    audio_track_id=audio_track_id,
                ),
            )
            echo_audio_track(result.audio_track)
            echo_job(result.job)

        run(action)

    @app.command("status")
    def job_status(job_id: str) -> None:
        runtime = runtime_factory()
        run(
            lambda: echo_job(
                runtime.use_cases.get_job_status.execute(
                    GetJobStatusCommand(job_id=job_id),
                ).job,
            ),
        )

    @app.command("run")
    def run_job(job_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.run_processing_job.execute(
                RunProcessingJobCommand(job_id=job_id),
            )
            echo_job(result.job)
            for warning in result.warnings:
                typer.echo(f"warning {warning.kind.value}: {warning.message}")

        run(action)

    @app.command("restart")
    def restart_job(job_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.restart_failed_processing_job.execute(
                RestartFailedProcessingJobCommand(job_id=job_id),
            )
            typer.echo(f"restarted_from={result.source_job.id}")
            echo_audio_track(result.audio_track)
            echo_job(result.job)

        run(action)

    @app.command("recreate-recap")
    def recreate_recap(job_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.generate_recap.execute(
                GenerateRecapCommand(job_id=job_id),
            )
            echo_job(result.job)

        run(action)

    return app
