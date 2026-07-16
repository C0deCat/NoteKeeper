"""Voice sample CLI commands."""

import typer

from notekeeper.application import AddVoiceSampleCommand, ListVoiceSamplesCommand

from .common import RuntimeFactory, duration, echo_metadata, inspect_audio, run


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Manage player voice samples.")

    @app.command("preflight")
    def preflight_sample(artifact_uri: str, artifact_kind: str = "file") -> None:
        runtime = runtime_factory()
        run(lambda: echo_metadata(inspect_audio(runtime, artifact_uri, artifact_kind)))

    @app.command("add")
    def add_sample(
        campaign_id: str,
        participant_id: str,
        artifact_uri: str,
        artifact_kind: str = "file",
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            echo_metadata(inspect_audio(runtime, artifact_uri, artifact_kind))
            result = runtime.use_cases.add_voice_sample.execute(
                AddVoiceSampleCommand(
                    campaign_id=campaign_id,
                    participant_id=participant_id,
                    artifact_uri=artifact_uri,
                    artifact_kind=artifact_kind,
                ),
            )
            typer.echo(f"voice_sample id={result.voice_sample.id}")

        run(action)

    @app.command("list")
    def list_samples(campaign_id: str, participant_id: str | None = None) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.list_voice_samples.execute(
                ListVoiceSamplesCommand(
                    campaign_id=campaign_id,
                    participant_id=participant_id,
                ),
            )
            for sample in result.voice_samples:
                typer.echo(
                    " ".join(
                        (
                            f"id={sample.id}",
                            f"participant={sample.participant_id}",
                            f"uri={sample.artifact.uri}",
                            f"duration={duration(sample.metadata)}",
                        ),
                    ),
                )

        run(action)

    return app
