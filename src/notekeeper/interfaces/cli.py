"""Typer command-line adapter."""

from __future__ import annotations

from collections.abc import Callable

import typer

from notekeeper.application import (
    AddParticipantToCampaignCommand,
    AddVoiceSampleCommand,
    ApplicationError,
    CreateCampaignCommand,
    CreateProcessingJobForAudioTrackCommand,
    ExportRecapMarkdownCommand,
    ExportTranscriptMarkdownCommand,
    GetCampaignCommand,
    GetJobStatusCommand,
    InspectAudioMetadataCommand,
    ListAudioTracksCommand,
    ListCampaignsCommand,
    ListJobsForCampaignCommand,
    ListParticipantsCommand,
    ListVoiceSamplesCommand,
    ManualSpeakerMappingCommand,
    PreviewRecapMarkdownCommand,
    PreviewTranscriptMarkdownCommand,
    ReviewSpeakerMappingsCommand,
    RestartFailedProcessingJobCommand,
    RunProcessingJobCommand,
    SubmitRecordingForProcessingCommand,
    SyncCampaignFolderCommand,
)
from notekeeper.domain import AudioMetadata, DomainError, JobStatus

from .contracts import InterfaceRuntime

RuntimeFactory = Callable[[], InterfaceRuntime]
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

    campaign_app = typer.Typer(help="Manage campaigns.")
    participant_app = typer.Typer(help="Manage campaign players.")
    sample_app = typer.Typer(help="Manage player voice samples.")
    recording_app = typer.Typer(help="Submit campaign recordings.")
    job_app = typer.Typer(help="Inspect and run processing jobs.")
    review_app = typer.Typer(help="Review speaker mappings.")
    transcript_app = typer.Typer(help="Preview and export transcripts.")
    recap_app = typer.Typer(help="Preview and export recaps.")

    @app.callback()
    def root(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            tui_runner(runtime_factory())

    @app.command("tui")
    def run_tui() -> None:
        tui_runner(runtime_factory())

    @campaign_app.command("create")
    def create_campaign(name: str) -> None:
        runtime = runtime_factory()
        _run(
            lambda: _echo_campaign(
                runtime.use_cases.create_campaign.execute(
                    CreateCampaignCommand(name=name),
                ).campaign,
            ),
        )

    @campaign_app.command("list")
    def list_campaigns() -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.list_campaigns.execute(ListCampaignsCommand())
            for campaign in result.campaigns:
                _echo_campaign(campaign)

        _run(action)

    @campaign_app.command("show")
    def show_campaign(campaign_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            campaign = runtime.use_cases.get_campaign.execute(
                GetCampaignCommand(campaign_id=campaign_id),
            ).campaign
            _echo_campaign(campaign)
            typer.echo(f"players={len(campaign.participants)}")
            typer.echo(f"voice_samples={len(campaign.voice_samples)}")
            typer.echo(f"recordings={len(campaign.audio_tracks)}")

        _run(action)

    @campaign_app.command("sync")
    def sync_campaign(campaign_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.sync_campaign_folder.execute(
                SyncCampaignFolderCommand(campaign_id=campaign_id),
            )
            _echo_sync_result(result)

        _run(action)

    @participant_app.command("add")
    def add_participant(campaign_id: str, display_name: str) -> None:
        runtime = runtime_factory()
        _run(
            lambda: _echo_participant(
                runtime.use_cases.add_participant.execute(
                    AddParticipantToCampaignCommand(
                        campaign_id=campaign_id,
                        display_name=display_name,
                    ),
                ).participant,
            ),
        )

    @participant_app.command("list")
    def list_participants(campaign_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.list_participants.execute(
                ListParticipantsCommand(campaign_id=campaign_id),
            )
            for participant in result.participants:
                _echo_participant(participant)

        _run(action)

    @sample_app.command("preflight")
    def preflight_sample(artifact_uri: str, artifact_kind: str = "file") -> None:
        runtime = runtime_factory()
        _run(lambda: _echo_metadata(_inspect(runtime, artifact_uri, artifact_kind)))

    @sample_app.command("add")
    def add_sample(
        campaign_id: str,
        participant_id: str,
        artifact_uri: str,
        artifact_kind: str = "file",
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            _echo_metadata(_inspect(runtime, artifact_uri, artifact_kind))
            result = runtime.use_cases.add_voice_sample.execute(
                AddVoiceSampleCommand(
                    campaign_id=campaign_id,
                    participant_id=participant_id,
                    artifact_uri=artifact_uri,
                    artifact_kind=artifact_kind,
                ),
            )
            typer.echo(f"voice_sample id={result.voice_sample.id}")

        _run(action)

    @sample_app.command("list")
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
                            f"duration={_duration(sample.metadata)}",
                        ),
                    ),
                )

        _run(action)

    @recording_app.command("preflight")
    def preflight_recording(artifact_uri: str, artifact_kind: str = "file") -> None:
        runtime = runtime_factory()
        _run(lambda: _echo_metadata(_inspect(runtime, artifact_uri, artifact_kind)))

    @recording_app.command("submit")
    def submit_recording(
        campaign_id: str,
        artifact_uri: str,
        title: str | None = None,
        artifact_kind: str = "file",
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            _echo_metadata(_inspect(runtime, artifact_uri, artifact_kind))
            result = runtime.use_cases.submit_recording_for_processing.execute(
                SubmitRecordingForProcessingCommand(
                    campaign_id=campaign_id,
                    artifact_uri=artifact_uri,
                    artifact_kind=artifact_kind,
                    title=title,
                ),
            )
            _echo_audio_track(result.audio_track)
            _echo_job(result.job)

        _run(action)

    @recording_app.command("list")
    def list_recordings(campaign_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.list_audio_tracks.execute(
                ListAudioTracksCommand(campaign_id=campaign_id),
            )
            for audio_track in result.audio_tracks:
                _echo_audio_track(audio_track)

        _run(action)

    @job_app.command("list")
    def list_jobs(campaign_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.list_jobs_for_campaign.execute(
                ListJobsForCampaignCommand(campaign_id=campaign_id),
            )
            for job in result.jobs:
                _echo_job(job)

        _run(action)

    @job_app.command("create")
    def create_job(audio_track_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.create_processing_job_for_audio_track.execute(
                CreateProcessingJobForAudioTrackCommand(
                    audio_track_id=audio_track_id,
                ),
            )
            _echo_audio_track(result.audio_track)
            _echo_job(result.job)

        _run(action)

    @job_app.command("status")
    def job_status(job_id: str) -> None:
        runtime = runtime_factory()
        _run(
            lambda: _echo_job(
                runtime.use_cases.get_job_status.execute(
                    GetJobStatusCommand(job_id=job_id),
                ).job,
            ),
        )

    @job_app.command("run")
    def run_job(job_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.run_processing_job.execute(
                RunProcessingJobCommand(job_id=job_id),
            )
            _echo_job(result.job)
            for warning in result.warnings:
                typer.echo(f"warning {warning.kind.value}: {warning.message}")

        _run(action)

    @job_app.command("restart")
    def restart_job(job_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.restart_failed_processing_job.execute(
                RestartFailedProcessingJobCommand(job_id=job_id),
            )
            typer.echo(f"restarted_from={result.source_job.id}")
            _echo_audio_track(result.audio_track)
            _echo_job(result.job)

        _run(action)

    @review_app.command("submit")
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
                    mappings=tuple(_parse_mapping(item) for item in mapping),
                ),
            )
            _echo_job(result.job)
            for warning in result.warnings:
                typer.echo(f"warning {warning.kind.value}: {warning.message}")

        _run(action)

    @transcript_app.command("preview")
    def preview_transcript(transcript_id: str) -> None:
        runtime = runtime_factory()
        _run(
            lambda: typer.echo(
                runtime.use_cases.preview_transcript_markdown.execute(
                    PreviewTranscriptMarkdownCommand(transcript_id=transcript_id),
                ).markdown,
                nl=False,
            ),
        )

    @transcript_app.command("export")
    def export_transcript(transcript_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.export_transcript_markdown.execute(
                ExportTranscriptMarkdownCommand(transcript_id=transcript_id),
            )
            typer.echo(runtime.format_artifact_location(result.artifact))

        _run(action)

    @recap_app.command("preview")
    def preview_recap(recap_id: str) -> None:
        runtime = runtime_factory()
        _run(
            lambda: typer.echo(
                runtime.use_cases.preview_recap_markdown.execute(
                    PreviewRecapMarkdownCommand(recap_id=recap_id),
                ).markdown,
                nl=False,
            ),
        )

    @recap_app.command("export")
    def export_recap(recap_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.export_recap_markdown.execute(
                ExportRecapMarkdownCommand(recap_id=recap_id),
            )
            typer.echo(runtime.format_artifact_location(result.artifact))

        _run(action)

    @cli.command("diagnostics")
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

    cli.add_typer(campaign_app, name="campaign")
    cli.add_typer(participant_app, name="participant")
    cli.add_typer(sample_app, name="sample")
    cli.add_typer(recording_app, name="recording")
    cli.add_typer(job_app, name="job")
    cli.add_typer(review_app, name="review")
    cli.add_typer(transcript_app, name="transcript")
    cli.add_typer(recap_app, name="recap")
    app.add_typer(cli, name="cli")
    return app


def _run(action: Callable[[], None]) -> None:
    try:
        action()
    except (ApplicationError, DomainError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _inspect(
    runtime: InterfaceRuntime,
    artifact_uri: str,
    artifact_kind: str,
) -> AudioMetadata:
    return runtime.use_cases.inspect_audio_metadata.execute(
        InspectAudioMetadataCommand(
            artifact_uri=artifact_uri,
            artifact_kind=artifact_kind,
        ),
    ).metadata


def _parse_mapping(value: str) -> ManualSpeakerMappingCommand:
    try:
        anonymous_label, participant_id = value.split("=", 1)
    except ValueError as exc:
        raise ValueError("mapping must use SPEAKER_00=participant-id form") from exc

    anonymous_label = anonymous_label.strip()
    participant_id = participant_id.strip()
    if not anonymous_label or not participant_id:
        raise ValueError("mapping must include speaker label and participant id")

    return ManualSpeakerMappingCommand(
        anonymous_label=anonymous_label,
        participant_id=participant_id,
        confidence=1.0,
    )


def _echo_campaign(campaign) -> None:
    typer.echo(f"id={campaign.id} name={campaign.name}")


def _echo_participant(participant) -> None:
    typer.echo(f"id={participant.id} name={participant.display_name}")


def _echo_audio_track(audio_track) -> None:
    title = audio_track.title or audio_track.artifact.uri
    typer.echo(
        " ".join(
            (
                f"audio_track id={audio_track.id}",
                f"title={title}",
                f"uri={audio_track.artifact.uri}",
                f"duration={_duration(audio_track.metadata)}",
            ),
        ),
    )


def _echo_job(job) -> None:
    parts = [
        f"job id={job.id}",
        f"status={_status(job.status)}",
        f"audio_track={job.audio_track_id}",
    ]
    if job.transcript_id is not None:
        parts.append(f"transcript={job.transcript_id}")
    if job.recap_id is not None:
        parts.append(f"recap={job.recap_id}")
    if job.error_message:
        parts.append(f"error={job.error_message}")
    typer.echo(" ".join(parts))


def _echo_sync_result(result) -> None:
    typer.echo(f"campaign id={result.campaign.id} name={result.campaign.name}")
    typer.echo(f"participants_created={result.participants_created}")
    typer.echo(f"voice_samples_added={result.voice_samples_added}")
    typer.echo(f"voice_samples_updated={result.voice_samples_updated}")
    typer.echo(f"voice_samples_deleted={result.voice_samples_deleted}")
    typer.echo(f"audio_tracks_added={result.audio_tracks_added}")
    typer.echo(f"audio_tracks_updated={result.audio_tracks_updated}")
    typer.echo(f"audio_tracks_deleted={result.audio_tracks_deleted}")
    typer.echo(f"pending_jobs_deleted={result.pending_jobs_deleted}")


def _echo_metadata(metadata: AudioMetadata) -> None:
    typer.echo(f"duration={_duration(metadata)}")
    if metadata.format:
        typer.echo(f"format={metadata.format}")
    if metadata.codec:
        typer.echo(f"codec={metadata.codec}")
    if metadata.sample_rate_hz:
        typer.echo(f"sample_rate_hz={metadata.sample_rate_hz}")
    if metadata.channels:
        typer.echo(f"channels={metadata.channels}")
    if metadata.file_size_bytes is not None:
        typer.echo(f"file_size_bytes={metadata.file_size_bytes}")


def _duration(metadata: AudioMetadata) -> str:
    return f"{metadata.duration_seconds:.2f}s"


def _status(status: JobStatus) -> str:
    return status.value
