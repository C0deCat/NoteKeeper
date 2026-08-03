import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from notekeeper.application import (
    CreateProcessingJobForAudioTrackCommand,
    CreateProcessingJobForAudioTrackResult,
    ExportMarkdownResult,
    GenerateRecapCommand,
    GenerateRecapResult,
    GetRecapGuidancesCommand,
    GetRecapGuidancesResult,
    GetJobStatusResult,
    InspectAudioMetadataResult,
    ListAudioTracksResult,
    ListCampaignsCommand,
    ListCampaignsResult,
    ListJobsForCampaignResult,
    ListParticipantsResult,
    ListVoiceSamplesResult,
    ManualSpeakerMappingCommand,
    MarkdownPreviewResult,
    ReviewSpeakerMappingsCommand,
    RestartFailedProcessingJobCommand,
    RestartFailedProcessingJobResult,
    SyncCampaignFolderCommand,
    SyncCampaignFolderResult,
    UpdateRecapGuidancesResult,
    UpdateRecapGuidancesCommand,
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
    Recap,
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
            artifact=ArtifactRef(
                uri="campaign-1/records/normalized/audio-track-1.wav",
            ),
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
            update_participant=FakeUseCase(None),
            delete_participant=FakeUseCase(None),
            add_voice_sample=FakeUseCase(None),
            list_voice_samples=FakeUseCase(ListVoiceSamplesResult(voice_samples=())),
            delete_voice_sample=FakeUseCase(None),
            register_audio_track=FakeUseCase(None),
            list_audio_tracks=FakeUseCase(
                ListAudioTracksResult(audio_tracks=(audio_track,)),
            ),
            update_audio_track=FakeUseCase(None),
            delete_audio_track=FakeUseCase(None),
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
            clear_failed_jobs_for_campaign=FakeUseCase(None),
            list_jobs_for_campaign=FakeUseCase(ListJobsForCampaignResult(jobs=(job,))),
            get_job_status=FakeUseCase(GetJobStatusResult(job=job)),
            review_speaker_mappings=FakeUseCase(GetJobStatusResult(job=job)),
            generate_recap=FakeUseCase(None),
            get_recap_guidances=FakeUseCase(
                GetRecapGuidancesResult(
                    campaign_id="campaign-1",
                    chunk_recap_guidances="chunk prompt",
                    combined_recap_guidances="combined prompt",
                ),
            ),
            update_recap_guidances=FakeUseCase(
                UpdateRecapGuidancesResult(
                    campaign_id="campaign-1",
                    chunk_recap_guidances="new chunk prompt",
                    combined_recap_guidances="new combined prompt",
                ),
            ),
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
            inspect_local_audio_file=FakeUseCase(None),
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


def test_cli_recap_prompts_show_outputs_campaign_json() -> None:
    runtime = FakeRuntime()
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(
        app,
        ["cli", "recap-prompts", "show", "campaign-1"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "chunk_recap_prompt": "chunk prompt",
        "combine_chunks_prompt": "combined prompt",
    }
    command = runtime.use_cases.get_recap_guidances.commands[0]
    assert isinstance(command, GetRecapGuidancesCommand)
    assert command.campaign_id == "campaign-1"


def test_cli_recap_prompts_set_reads_both_utf8_files(tmp_path: Path) -> None:
    runtime = FakeRuntime()
    chunk_file = tmp_path / "chunk.txt"
    combined_file = tmp_path / "combined.txt"
    chunk_file.write_text("Новый chunk", encoding="utf-8")
    combined_file.write_text("Новый combined", encoding="utf-8")
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(
        app,
        [
            "cli",
            "recap-prompts",
            "set",
            "campaign-1",
            "--chunk-file",
            str(chunk_file),
            "--combined-file",
            str(combined_file),
        ],
    )

    assert result.exit_code == 0
    command = runtime.use_cases.update_recap_guidances.commands[0]
    assert isinstance(command, UpdateRecapGuidancesCommand)
    assert command.chunk_recap_guidances == "Новый chunk"
    assert command.combined_recap_guidances == "Новый combined"


def test_cli_recap_prompts_set_reports_unreadable_file(tmp_path: Path) -> None:
    runtime = FakeRuntime()
    combined_file = tmp_path / "combined.txt"
    combined_file.write_text("combined", encoding="utf-8")
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(
        app,
        [
            "cli",
            "recap-prompts",
            "set",
            "campaign-1",
            "--chunk-file",
            str(tmp_path / "missing.txt"),
            "--combined-file",
            str(combined_file),
        ],
    )

    assert result.exit_code == 1
    assert "could not read prompt file" in result.output
    assert runtime.use_cases.update_recap_guidances.commands == []


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


def test_cli_job_recreate_recap_uses_existing_generate_recap_use_case() -> None:
    runtime = FakeRuntime()
    job = replace(
        runtime.use_cases.get_job_status.result.job,
        transcript_id="transcript-1",
        recap_id="recap-new",
    )
    recap = Recap(
        id="recap-new",
        transcript_id="transcript-1",
        markdown="# Recap",
    )
    runtime.use_cases.generate_recap.result = GenerateRecapResult(
        job=job,
        recap=recap,
    )
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(
        app,
        ["cli", "job", "recreate-recap", "job-1"],
    )

    assert result.exit_code == 0
    assert "job id=job-1" in result.output
    assert "transcript=transcript-1" in result.output
    assert "recap=recap-new" in result.output
    command = runtime.use_cases.generate_recap.commands[0]
    assert isinstance(command, GenerateRecapCommand)
    assert command.job_id == "job-1"


def test_cli_review_submit_supports_player_custom_and_keep_decisions() -> None:
    runtime = FakeRuntime()
    runtime.use_cases.review_speaker_mappings.result = SimpleNamespace(
        job=runtime.use_cases.get_job_status.result.job,
        warnings=(),
    )
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(
        app,
        [
            "cli",
            "review",
            "submit",
            "job-1",
            "--mapping",
            "SPEAKER_00=participant-1",
            "--label",
            "SPEAKER_01=Random Guest",
            "--keep",
            "SPEAKER_02",
        ],
    )

    assert result.exit_code == 0
    command = runtime.use_cases.review_speaker_mappings.commands[0]
    assert isinstance(command, ReviewSpeakerMappingsCommand)
    assert command.mappings == (
        ManualSpeakerMappingCommand(
            anonymous_label="SPEAKER_00",
            participant_id="participant-1",
            confidence=1.0,
        ),
        ManualSpeakerMappingCommand(
            anonymous_label="SPEAKER_01",
            named_label="Random Guest",
            confidence=1.0,
        ),
        ManualSpeakerMappingCommand(
            anonymous_label="SPEAKER_02",
            named_label="SPEAKER_02",
            confidence=1.0,
        ),
    )


def test_cli_review_submit_requires_at_least_one_decision() -> None:
    runtime = FakeRuntime()
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(app, ["cli", "review", "submit", "job-1"])

    assert result.exit_code == 1
    assert "at least one --mapping, --label, or --keep is required" in result.output
    assert runtime.use_cases.review_speaker_mappings.commands == []


def test_cli_diagnostics_does_not_print_secret_values() -> None:
    runtime = FakeRuntime()
    app = build_app(lambda: runtime, lambda value: None)

    result = CliRunner().invoke(app, ["cli", "diagnostics"])

    assert result.exit_code == 0
    assert "deepseek_configured=True" in result.output
    assert "huggingface_configured=True" in result.output
    assert "secret" not in result.output
