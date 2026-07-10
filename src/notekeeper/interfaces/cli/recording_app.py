"""Recording CLI commands."""

import typer

from notekeeper.application import ListAudioTracksCommand, SubmitRecordingForProcessingCommand

from .common import (
    RuntimeFactory,
    echo_audio_track,
    echo_job,
    echo_metadata,
    inspect_audio,
    run,
)


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Submit campaign recordings.")

    @app.command("preflight")
    def preflight_recording(artifact_uri: str, artifact_kind: str = "file") -> None:
        runtime = runtime_factory()
        run(lambda: echo_metadata(inspect_audio(runtime, artifact_uri, artifact_kind)))

    @app.command("submit")
    def submit_recording(
        campaign_id: str,
        artifact_uri: str,
        title: str | None = None,
        artifact_kind: str = "file",
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            echo_metadata(inspect_audio(runtime, artifact_uri, artifact_kind))
            result = runtime.use_cases.submit_recording_for_processing.execute(
                SubmitRecordingForProcessingCommand(
                    campaign_id=campaign_id,
                    artifact_uri=artifact_uri,
                    artifact_kind=artifact_kind,
                    title=title,
                ),
            )
            echo_audio_track(result.audio_track)
            echo_job(result.job)

        run(action)

    @app.command("list")
    def list_recordings(campaign_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.list_audio_tracks.execute(
                ListAudioTracksCommand(campaign_id=campaign_id),
            )
            for audio_track in result.audio_tracks:
                echo_audio_track(audio_track)

        run(action)

    return app
