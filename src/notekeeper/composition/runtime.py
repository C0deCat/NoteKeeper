"""Runtime assembly for user interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from notekeeper.application import (
    AddParticipantToCampaign,
    AddVoiceSample,
    CreateCampaign,
    CreateProcessingJobForAudioTrack,
    ExportRecapMarkdown,
    ExportTranscriptMarkdown,
    GenerateRecap,
    GetCampaign,
    GetJobStatus,
    InspectAudioMetadata,
    ListAudioTracks,
    ListCampaigns,
    ListJobsForCampaign,
    ListJobsForCampaignCommand,
    ListParticipants,
    ListVoiceSamples,
    PreviewRecapMarkdown,
    PreviewTranscriptMarkdown,
    RegisterAudioTrack,
    ReviewSpeakerMappings,
    RunProcessingJob,
    SubmitRecordingForProcessing,
    SyncCampaignFolder,
)
from notekeeper.application.errors import ApplicationError
from notekeeper.domain import ArtifactRef
from notekeeper.interfaces import InterfaceRuntime, RuntimeDiagnostics, Stage1UseCases

from .factory import InfrastructureBundle, build_infrastructure
from .settings import NoteKeeperSettings


@dataclass(frozen=True, slots=True)
class NoteKeeperRuntime:
    settings: NoteKeeperSettings
    use_cases: Stage1UseCases
    infrastructure: InfrastructureBundle

    def diagnostics(self, campaign_id: str | None = None) -> RuntimeDiagnostics:
        return RuntimeDiagnostics(
            storage_root=_path_text(self.settings.storage_root),
            sqlite_path=_path_text(self.settings.sqlite_path),
            processing_work_root=_path_text(self.settings.processing_work_root),
            recap_prompts_file=_path_text(self.settings.recap_prompts_file),
            whisperx_model_name=self.settings.whisperx_model_name,
            whisperx_device=self.settings.whisperx_device,
            whisperx_compute_type=self.settings.whisperx_compute_type,
            deepseek_configured=bool(self.settings.deepseek_api_key),
            huggingface_configured=bool(self.settings.whisperx_hf_token),
            recent_messages=_recent_messages(self.use_cases, campaign_id),
        )

    def format_artifact_location(self, artifact: ArtifactRef) -> str:
        if artifact.kind != "file":
            return artifact.uri

        path_for_uri = getattr(
            self.infrastructure.artifact_storage,
            "path_for_uri",
            None,
        )
        if callable(path_for_uri):
            return str(path_for_uri(artifact.uri).resolve(strict=False))

        return str((self.settings.storage_root / Path(artifact.uri)).resolve(strict=False))


def build_runtime(settings: NoteKeeperSettings | None = None) -> NoteKeeperRuntime:
    infrastructure = build_infrastructure(settings)
    return NoteKeeperRuntime(
        settings=infrastructure.settings,
        use_cases=build_stage1_use_cases(infrastructure),
        infrastructure=infrastructure,
    )


def build_stage1_use_cases(infrastructure: InfrastructureBundle) -> Stage1UseCases:
    return Stage1UseCases(
        create_campaign=CreateCampaign(
            infrastructure.campaign_repository,
            infrastructure.id_generator,
            infrastructure.artifact_storage,
        ),
        get_campaign=GetCampaign(infrastructure.campaign_repository),
        list_campaigns=ListCampaigns(infrastructure.campaign_repository),
        add_participant=AddParticipantToCampaign(
            infrastructure.campaign_repository,
            infrastructure.id_generator,
        ),
        list_participants=ListParticipants(infrastructure.campaign_repository),
        add_voice_sample=AddVoiceSample(
            infrastructure.campaign_repository,
            infrastructure.metadata_reader,
            infrastructure.id_generator,
        ),
        list_voice_samples=ListVoiceSamples(infrastructure.campaign_repository),
        register_audio_track=RegisterAudioTrack(
            infrastructure.campaign_repository,
            infrastructure.metadata_reader,
            infrastructure.id_generator,
        ),
        list_audio_tracks=ListAudioTracks(infrastructure.campaign_repository),
        create_processing_job_for_audio_track=CreateProcessingJobForAudioTrack(
            infrastructure.campaign_repository,
            infrastructure.audio_track_repository,
            infrastructure.job_repository,
            infrastructure.clock,
            infrastructure.id_generator,
        ),
        submit_recording_for_processing=SubmitRecordingForProcessing(
            infrastructure.campaign_repository,
            infrastructure.audio_track_repository,
            infrastructure.job_repository,
            infrastructure.metadata_reader,
            infrastructure.clock,
            infrastructure.id_generator,
        ),
        run_processing_job=RunProcessingJob(
            infrastructure.campaign_repository,
            infrastructure.audio_track_repository,
            infrastructure.transcript_repository,
            infrastructure.recap_repository,
            infrastructure.job_repository,
            infrastructure.audio_processor,
            infrastructure.transcriber,
            infrastructure.speaker_identifier,
            infrastructure.speaker_mapping_repository,
            infrastructure.tokenizer,
            infrastructure.recap_generator,
            infrastructure.clock,
            infrastructure.id_generator,
        ),
        list_jobs_for_campaign=ListJobsForCampaign(
            infrastructure.campaign_repository,
            infrastructure.job_repository,
        ),
        get_job_status=GetJobStatus(infrastructure.job_repository),
        review_speaker_mappings=ReviewSpeakerMappings(
            infrastructure.campaign_repository,
            infrastructure.transcript_repository,
            infrastructure.recap_repository,
            infrastructure.job_repository,
            infrastructure.speaker_mapping_repository,
            infrastructure.tokenizer,
            infrastructure.recap_generator,
            infrastructure.clock,
            infrastructure.id_generator,
        ),
        generate_recap=GenerateRecap(
            infrastructure.transcript_repository,
            infrastructure.recap_repository,
            infrastructure.tokenizer,
            infrastructure.recap_generator,
            infrastructure.id_generator,
        ),
        export_transcript_markdown=ExportTranscriptMarkdown(
            infrastructure.transcript_repository,
            infrastructure.artifact_storage,
        ),
        export_recap_markdown=ExportRecapMarkdown(
            infrastructure.recap_repository,
            infrastructure.artifact_storage,
        ),
        preview_transcript_markdown=PreviewTranscriptMarkdown(
            infrastructure.transcript_repository,
        ),
        preview_recap_markdown=PreviewRecapMarkdown(infrastructure.recap_repository),
        inspect_audio_metadata=InspectAudioMetadata(infrastructure.metadata_reader),
        sync_campaign_folder=SyncCampaignFolder(
            infrastructure.campaign_repository,
            infrastructure.job_repository,
            infrastructure.folder_scanner,
            infrastructure.metadata_reader,
            infrastructure.id_generator,
        ),
    )


def _recent_messages(
    use_cases: Stage1UseCases,
    campaign_id: str | None,
) -> tuple[str, ...]:
    if campaign_id is None:
        return ()

    try:
        jobs = use_cases.list_jobs_for_campaign.execute(
            ListJobsForCampaignCommand(campaign_id=campaign_id),
        ).jobs
    except ApplicationError as exc:
        return (str(exc),)

    messages: list[str] = []
    for job in reversed(jobs):
        if job.error_message:
            messages.append(f"{job.id}: {job.error_message}")
        for warning in job.warnings:
            messages.append(f"{job.id}: {warning.message}")
        if len(messages) >= 8:
            break
    return tuple(messages[:8])


def _path_text(path: Path) -> str:
    return str(path.resolve(strict=False))
