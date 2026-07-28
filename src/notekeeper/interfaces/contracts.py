"""Contracts shared by UI adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from notekeeper.application import (
    AddParticipantToCampaign,
    AddVoiceSample,
    CancelProcessingJob,
    ClearFailedJobsForCampaign,
    CreateCampaign,
    CreateProcessingJobForAudioTrack,
    DeleteAudioTrack,
    DeleteCampaign,
    DeleteParticipant,
    DeleteProcessingJob,
    DeleteVoiceSample,
    ExportRecapMarkdown,
    ExportTranscriptMarkdown,
    GenerateRecap,
    GetCampaign,
    GetJobStatus,
    InspectAudioMetadata,
    InspectLocalAudioFile,
    ListAudioTracks,
    ListCampaigns,
    ListJobsForCampaign,
    ListParticipants,
    ListVoiceSamples,
    PreviewRecapMarkdown,
    PreviewTranscriptMarkdown,
    RegisterAudioTrack,
    RestartFailedProcessingJob,
    RestartProcessingJob,
    ReviewSpeakerMappings,
    RunProcessingJob,
    SubmitRecordingForProcessing,
    SyncCampaignFolder,
    UpdateAudioTrack,
    UpdateCampaign,
    UpdateParticipant,
)
from notekeeper.domain import ArtifactRef
from notekeeper.application.ports import ProgressEventStream


@dataclass(frozen=True, slots=True)
class Stage1UseCases:
    create_campaign: CreateCampaign
    get_campaign: GetCampaign
    list_campaigns: ListCampaigns
    update_campaign: UpdateCampaign
    delete_campaign: DeleteCampaign
    add_participant: AddParticipantToCampaign
    list_participants: ListParticipants
    update_participant: UpdateParticipant
    delete_participant: DeleteParticipant
    add_voice_sample: AddVoiceSample
    list_voice_samples: ListVoiceSamples
    delete_voice_sample: DeleteVoiceSample
    register_audio_track: RegisterAudioTrack
    list_audio_tracks: ListAudioTracks
    update_audio_track: UpdateAudioTrack
    delete_audio_track: DeleteAudioTrack
    create_processing_job_for_audio_track: CreateProcessingJobForAudioTrack
    submit_recording_for_processing: SubmitRecordingForProcessing
    run_processing_job: RunProcessingJob
    restart_failed_processing_job: RestartFailedProcessingJob
    clear_failed_jobs_for_campaign: ClearFailedJobsForCampaign
    list_jobs_for_campaign: ListJobsForCampaign
    get_job_status: GetJobStatus
    review_speaker_mappings: ReviewSpeakerMappings
    generate_recap: GenerateRecap
    export_transcript_markdown: ExportTranscriptMarkdown
    export_recap_markdown: ExportRecapMarkdown
    preview_transcript_markdown: PreviewTranscriptMarkdown
    preview_recap_markdown: PreviewRecapMarkdown
    inspect_audio_metadata: InspectAudioMetadata
    inspect_local_audio_file: InspectLocalAudioFile
    sync_campaign_folder: SyncCampaignFolder
    restart_processing_job: RestartProcessingJob | None = None
    delete_processing_job: DeleteProcessingJob | None = None
    cancel_processing_job: CancelProcessingJob | None = None


@dataclass(frozen=True, slots=True)
class RuntimeDiagnostics:
    storage_root: str
    sqlite_path: str
    processing_work_root: str
    recap_prompts_file: str
    whisperx_model_name: str
    whisperx_device: str
    whisperx_compute_type: str
    whisperx_vad_method: str
    deepseek_configured: bool
    huggingface_configured: bool
    recent_messages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "recent_messages", tuple(self.recent_messages))


class InterfaceRuntime(Protocol):
    use_cases: Stage1UseCases
    progress_events: ProgressEventStream

    def diagnostics(self, campaign_id: str | None = None) -> RuntimeDiagnostics: ...

    def format_artifact_location(self, artifact: ArtifactRef) -> str: ...
