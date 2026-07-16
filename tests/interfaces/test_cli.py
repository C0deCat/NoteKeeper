from datetime import datetime

from typer.testing import CliRunner

from notekeeper.application import (
    CreateProcessingJobForAudioTrackCommand,
    CreateProcessingJobForAudioTrackResult,
    ExportMarkdownResult,
    GetJobStatusResult,
    InspectAudioMetadataResult,
    ListAudioTracksResult,
    ListCampaignsCommand,
    ListCampaignsResult,
    ListJobsForCampaignResult,
    ListParticipantsResult,
    ListVoiceSamplesResult,
    MarkdownPreviewResult,
    RestartFailedProcessingJobCommand,
    RestartFailedProcessingJobResult,
    SyncCampaignFolderCommand,
    SyncCampaignFolderResult,
)
from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrack,
    Campaign,
    CampaignId,
    JobStatus,
    Participant,
    ParticipantId,
    ProcessingJob,
)
from notekeeper.interfaces import RuntimeDiagnostics, Stage1UseCases
from notekeeper.interfaces.cli import build_app


class FakeUseCase:
    def __init__(self, result) -> None:
        self.result = result
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        return self.result


class FakeRuntime:
    def __init__(self) -> None:
        campaign = Campaign(id=CampaignId("campaign-1"), name="Demo")
        participant = Participant(
            id=ParticipantId("participant-1"),
            campaign_id=campaign.id,
            display_name="Alice",
        )
        job = ProcessingJob(
            id="job-1",
            campaign_id=campaign.id,
            audio_track_id="audio-track-1",
            status=JobStatus.PENDING,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
        failed_job = ProcessingJob(
            id="job-failed",
            campaign_id=campaign.id,
            audio_track_id="audio-track-1",
            status=JobStatus.FAILED,
            created_at=datetime(2026, 1, 2),
            updated_at=datetime(2026, 1, 2),
            error_message="failed",
        )
        metadata = AudioMetadata(duration_seconds=12, format="wav")
        audio_track = AudioTrack(
            id="audio-track-1",
            campaign_id=campaign.id,
            artifact=ArtifactRef(uri="sessions/session-1.wav"),
            metadata=metadata,
            title="Session 1",
        )
        self.use_cases = Stage1UseCases(
            create_campaign=FakeUseCase(None),
            get_campaign=FakeUseCase(None),
            list_campaigns=FakeUseCase(ListCampaignsResult(campaigns=(campaign,))),
            update_campaign=FakeUseCase(None),
            delete_campaign=FakeUseCase(None),
            add_participant=FakeUseCase(None),
            list_participants=FakeUseCase(
                ListParticipantsResult(participants=(participant,)),
            ),
            add_voice_sample=FakeUseCase(None),
            list_voice_samples=FakeUseCase(ListVoiceSamplesResult(voice_samples=())),
            register_audio_track=FakeUseCase(None),
            list_audio_tracks=FakeUseCase(
                ListAudioTracksResult(audio_tracks=(audio_track,)),
            ),
            create_processing_job_for_audio_track=FakeUseCase(
                CreateProcessingJobForAudioTrackResult(
                    campaign=campaign,
                    audio_track=audio_track,
                    job=job,
                ),
            ),
            submit_recording_for_processing=FakeUseCase(None),
            run_processing_job=FakeUseCase(GetJobStatusResult(job=job)),
            restart_failed_processing_job=FakeUseCase(
                RestartFailedProcessingJobResult(
                    campaign=campaign,
                    audio_track=audio_track,
                    source_job=failed_job,
                    job=job,
                ),
            ),
            list_jobs_for_campaign=FakeUseCase(ListJobsForCampaignResult(jobs=(job,))),
            get_job_status=FakeUseCase(GetJobStatusResult(job=job)),
            review_speaker_mappings=FakeUseCase(GetJobStatusResult(job=job)),
            generate_recap=FakeUseCase(None),
            export_transcript_markdown=FakeUseCase(
                ExportMarkdownResult(artifact=ArtifactRef(uri="exports/t.md")),
            ),
            export_recap_markdown=FakeUseCase(
                ExportMarkdownResult(artifact=ArtifactRef(uri="exports/r.md")),
            ),
            preview_transcript_markdown=FakeUseCase(
                MarkdownPreviewResult(markdown="# Transcript\n"),
            ),
            preview_recap_markdown=FakeUseCase(
                MarkdownPreviewResult(markdown="# Recap\n"),
            ),
            inspect_audio_metadata=FakeUseCase(
                InspectAudioMetadataResult(
                    artifact=ArtifactRef(uri="sample.wav"),
                    metadata=metadata,
                ),
            ),
            sync_campaign_folder=FakeUseCase(
                SyncCampaignFolderResult(
                    campaign=campaign,
                    participants_created=1,
                    voice_samples_added=2,
                    voice_samples_updated=3,
                    voice_samples_deleted=4,
                    audio_tracks_added=5,
                    audio_tracks_updated=6,
                    audio_tracks_deleted=7,
                    pending_jobs_deleted=8,
                ),
            ),
        )

    def diagnostics(self, campaign_id: str | None = None) -> RuntimeDiagnostics:
        return RuntimeDiagnostics(
            storage_root="artifacts",
            sqlite_path="notekeeper.sqlite3",
            processing_work_root="work",
            recap_prompts_file="recap_prompts.json",
            whisperx_model_name="small",
            whisperx_device="cpu",
            whisperx_compute_type="int8",
            whisperx_vad_method="silero",
            deepseek_configured=True,
            huggingface_configured=True,
        )

    def format_artifact_location(self, artifact: ArtifactRef) -> str:
        return f"local:{artifact.uri}"


def test_root_without_args_runs_tui() -> None:
    runtime = FakeRuntime()
    launched = []
    app = build_app(lambda: runtime, lambda value: launched.append(value))

    result = CliRunner().invoke(app, [])

    assert result.exit_code == 0
    assert launched == [runtime]


def test_cli_campaign_list_uses_runtime_use_case() -> None:
    runtime = FakeRuntime()
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(app, ["cli", "campaign", "list"])

    assert result.exit_code == 0
    assert "id=campaign-1 name=Demo" in result.output
    assert isinstance(
        runtime.use_cases.list_campaigns.commands[0],
        ListCampaignsCommand,
    )


def test_cli_campaign_sync_uses_runtime_use_case() -> None:
    runtime = FakeRuntime()
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(app, ["cli", "campaign", "sync", "campaign-1"])

    assert result.exit_code == 0
    assert "campaign id=campaign-1 name=Demo" in result.output
    assert "participants_created=1" in result.output
    assert "voice_samples_added=2" in result.output
    assert "voice_samples_updated=3" in result.output
    assert "voice_samples_deleted=4" in result.output
    assert "audio_tracks_added=5" in result.output
    assert "audio_tracks_updated=6" in result.output
    assert "audio_tracks_deleted=7" in result.output
    assert "pending_jobs_deleted=8" in result.output
    command = runtime.use_cases.sync_campaign_folder.commands[0]
    assert isinstance(command, SyncCampaignFolderCommand)
    assert command.campaign_id == "campaign-1"


def test_cli_job_create_uses_existing_audio_track_use_case() -> None:
    runtime = FakeRuntime()
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(app, ["cli", "job", "create", "audio-track-1"])

    assert result.exit_code == 0
    assert "audio_track id=audio-track-1" in result.output
    assert "job id=job-1" in result.output
    command = runtime.use_cases.create_processing_job_for_audio_track.commands[0]
    assert isinstance(command, CreateProcessingJobForAudioTrackCommand)
    assert command.audio_track_id == "audio-track-1"


def test_cli_job_restart_uses_failed_restart_use_case() -> None:
    runtime = FakeRuntime()
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(app, ["cli", "job", "restart", "job-failed"])

    assert result.exit_code == 0
    assert "restarted_from=job-failed" in result.output
    assert "audio_track id=audio-track-1" in result.output
    assert "job id=job-1" in result.output
    command = runtime.use_cases.restart_failed_processing_job.commands[0]
    assert isinstance(command, RestartFailedProcessingJobCommand)
    assert command.job_id == "job-failed"


def test_cli_diagnostics_does_not_print_secret_values() -> None:
    runtime = FakeRuntime()
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(app, ["cli", "diagnostics"])

    assert result.exit_code == 0
    assert "deepseek_configured=True" in result.output
    assert "huggingface_configured=True" in result.output
    assert "secret" not in result.output
