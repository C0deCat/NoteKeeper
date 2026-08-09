"""Contracts shared by UI adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from notekeeper.application import (
    AddParticipantToCampaignCommand,
    AddParticipantToCampaignResult,
    AddVoiceSampleCommand,
    AddVoiceSampleResult,
    CancelProcessingJob,
    ClearFailedJobsForCampaign,
    CreateCampaign,
    CreateProcessingJobForAudioTrack,
    DeleteAudioTrackCommand,
    DeleteAudioTrackResult,
    DeleteCampaign,
    DeleteParticipantCommand,
    DeleteParticipantResult,
    DeleteProcessingJob,
    DeleteVoiceSampleCommand,
    DeleteVoiceSampleResult,
    ExportRecapMarkdown,
    ExportTranscriptMarkdown,
    GenerateRecap,
    GetCampaign,
    GetJobStatus,
    GetRecapGuidances,
    InspectAudioMetadata,
    InspectLocalAudioFile,
    ListAudioTracks,
    ListCampaigns,
    ListJobsForCampaign,
    ListParticipants,
    ListVoiceSamples,
    PreviewRecapMarkdown,
    PreviewTranscriptMarkdown,
    QueueProcessingJob,
    RegisterAudioTrackCommand,
    RegisterAudioTrackResult,
    RestartFailedProcessingJob,
    RestartProcessingJob,
    ReviewSpeakerMappings,
    SubmitRecordingForProcessingCommand,
    SubmitRecordingForProcessingResult,
    SyncCampaignFolderCommand,
    SyncCampaignFolderResult,
    UpdateAudioTrackCommand,
    UpdateAudioTrackResult,
    UpdateCampaignCommand,
    UpdateCampaignResult,
    UpdateParticipantCommand,
    UpdateParticipantResult,
    UpdateRecapGuidances,
    UpdateVoiceSampleCommand,
    UpdateVoiceSampleResult,
)
from notekeeper.application.ports import DashboardEventStream, ProgressEventStream
from notekeeper.application.use_cases.utils import CampaignMutationUseCase
from notekeeper.domain import ArtifactRef, ProcessingJob


@dataclass(frozen=True, slots=True)
class Stage1UseCases:
    create_campaign: CreateCampaign
    get_campaign: GetCampaign
    list_campaigns: ListCampaigns
    update_campaign: CampaignMutationUseCase[
        UpdateCampaignCommand,
        UpdateCampaignResult,
    ]
    delete_campaign: DeleteCampaign
    add_participant: CampaignMutationUseCase[
        AddParticipantToCampaignCommand,
        AddParticipantToCampaignResult,
    ]
    list_participants: ListParticipants
    update_participant: CampaignMutationUseCase[
        UpdateParticipantCommand,
        UpdateParticipantResult,
    ]
    delete_participant: CampaignMutationUseCase[
        DeleteParticipantCommand,
        DeleteParticipantResult,
    ]
    add_voice_sample: CampaignMutationUseCase[
        AddVoiceSampleCommand,
        AddVoiceSampleResult,
    ]
    list_voice_samples: ListVoiceSamples
    delete_voice_sample: CampaignMutationUseCase[
        DeleteVoiceSampleCommand,
        DeleteVoiceSampleResult,
    ]
    register_audio_track: CampaignMutationUseCase[
        RegisterAudioTrackCommand,
        RegisterAudioTrackResult,
    ]
    list_audio_tracks: ListAudioTracks
    update_audio_track: CampaignMutationUseCase[
        UpdateAudioTrackCommand,
        UpdateAudioTrackResult,
    ]
    delete_audio_track: CampaignMutationUseCase[
        DeleteAudioTrackCommand,
        DeleteAudioTrackResult,
    ]
    create_processing_job_for_audio_track: CreateProcessingJobForAudioTrack
    submit_recording_for_processing: CampaignMutationUseCase[
        SubmitRecordingForProcessingCommand,
        SubmitRecordingForProcessingResult,
    ]
    run_processing_job: QueueProcessingJob
    restart_failed_processing_job: RestartFailedProcessingJob
    clear_failed_jobs_for_campaign: ClearFailedJobsForCampaign
    list_jobs_for_campaign: ListJobsForCampaign
    get_job_status: GetJobStatus
    review_speaker_mappings: ReviewSpeakerMappings
    generate_recap: GenerateRecap
    get_recap_guidances: GetRecapGuidances
    update_recap_guidances: UpdateRecapGuidances
    export_transcript_markdown: ExportTranscriptMarkdown
    export_recap_markdown: ExportRecapMarkdown
    preview_transcript_markdown: PreviewTranscriptMarkdown
    preview_recap_markdown: PreviewRecapMarkdown
    inspect_audio_metadata: InspectAudioMetadata
    inspect_local_audio_file: InspectLocalAudioFile
    sync_campaign_folder: CampaignMutationUseCase[
        SyncCampaignFolderCommand,
        SyncCampaignFolderResult,
    ]
    queue_processing_job: QueueProcessingJob | None = None
    update_voice_sample: (
        CampaignMutationUseCase[
            UpdateVoiceSampleCommand,
            UpdateVoiceSampleResult,
        ]
        | None
    ) = None
    restart_processing_job: RestartProcessingJob | None = None
    delete_processing_job: DeleteProcessingJob | None = None
    cancel_processing_job: CancelProcessingJob | None = None


@dataclass(frozen=True, slots=True)
class RuntimeDiagnostics:
    storage_root: str
    sqlite_path: str
    processing_work_root: str
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
    @property
    def use_cases(self) -> Stage1UseCases: ...

    @property
    def progress_events(self) -> ProgressEventStream: ...

    @property
    def dashboard_events(self) -> DashboardEventStream: ...

    def start_job_manager(self, *, recover_queued: bool = True) -> None: ...

    def shutdown_job_manager(self) -> None: ...

    def wait_for_job(self, job_id: str) -> ProcessingJob: ...

    def diagnostics(self, campaign_id: str | None = None) -> RuntimeDiagnostics: ...

    def format_artifact_location(self, artifact: ArtifactRef) -> str: ...
