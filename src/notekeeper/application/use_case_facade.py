"""Typed groups of application use cases exposed to interface adapters."""

from dataclasses import dataclass

from .commands import (
    AddParticipantToCampaignCommand,
    AddVoiceSampleCommand,
    DeleteAudioTrackCommand,
    DeleteCampaignCommand,
    DeleteParticipantCommand,
    DeleteVoiceSampleCommand,
    RegisterAudioTrackCommand,
    SubmitRecordingForProcessingCommand,
    SyncCampaignFolderCommand,
    UpdateAudioTrackCommand,
    UpdateCampaignCommand,
    UpdateParticipantCommand,
    UpdateRecapGuidancesCommand,
    UpdateVoiceSampleCommand,
)
from .results import (
    AddParticipantToCampaignResult,
    AddVoiceSampleResult,
    DeleteAudioTrackResult,
    DeleteCampaignResult,
    DeleteParticipantResult,
    DeleteVoiceSampleResult,
    RegisterAudioTrackResult,
    SubmitRecordingForProcessingResult,
    SyncCampaignFolderResult,
    UpdateAudioTrackResult,
    UpdateCampaignResult,
    UpdateParticipantResult,
    UpdateRecapGuidancesResult,
    UpdateVoiceSampleResult,
)
from .use_cases import (
    CancelProcessingJob,
    ClearFailedJobsForCampaign,
    CreateCampaign,
    CreateProcessingJobForAudioTrack,
    DeleteProcessingJob,
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
    RestartFailedProcessingJob,
    RestartProcessingJob,
    ReviewSpeakerMappings,
)
from .use_cases.utils import CampaignMutationUseCase
from .settings_service import SettingsService


@dataclass(frozen=True, slots=True)
class CampaignUseCases:
    create: CreateCampaign
    get: GetCampaign
    list: ListCampaigns
    update: CampaignMutationUseCase[UpdateCampaignCommand, UpdateCampaignResult]
    delete: CampaignMutationUseCase[DeleteCampaignCommand, DeleteCampaignResult]
    sync_folder: CampaignMutationUseCase[
        SyncCampaignFolderCommand, SyncCampaignFolderResult
    ]
    get_recap_guidances: GetRecapGuidances
    update_recap_guidances: CampaignMutationUseCase[
        UpdateRecapGuidancesCommand, UpdateRecapGuidancesResult
    ]


@dataclass(frozen=True, slots=True)
class ParticipantUseCases:
    add: CampaignMutationUseCase[
        AddParticipantToCampaignCommand, AddParticipantToCampaignResult
    ]
    list: ListParticipants
    update: CampaignMutationUseCase[UpdateParticipantCommand, UpdateParticipantResult]
    delete: CampaignMutationUseCase[DeleteParticipantCommand, DeleteParticipantResult]


@dataclass(frozen=True, slots=True)
class SampleUseCases:
    add: CampaignMutationUseCase[AddVoiceSampleCommand, AddVoiceSampleResult]
    list: ListVoiceSamples
    update: CampaignMutationUseCase[UpdateVoiceSampleCommand, UpdateVoiceSampleResult]
    delete: CampaignMutationUseCase[DeleteVoiceSampleCommand, DeleteVoiceSampleResult]


@dataclass(frozen=True, slots=True)
class RecordingUseCases:
    register: CampaignMutationUseCase[
        RegisterAudioTrackCommand, RegisterAudioTrackResult
    ]
    list: ListAudioTracks
    update: CampaignMutationUseCase[UpdateAudioTrackCommand, UpdateAudioTrackResult]
    delete: CampaignMutationUseCase[DeleteAudioTrackCommand, DeleteAudioTrackResult]
    submit_for_processing: CampaignMutationUseCase[
        SubmitRecordingForProcessingCommand, SubmitRecordingForProcessingResult
    ]


@dataclass(frozen=True, slots=True)
class JobUseCases:
    create: CreateProcessingJobForAudioTrack
    queue: QueueProcessingJob
    restart_failed: RestartFailedProcessingJob
    restart: RestartProcessingJob
    clear_failed: ClearFailedJobsForCampaign
    delete: DeleteProcessingJob
    cancel: CancelProcessingJob
    list_for_campaign: ListJobsForCampaign
    get_status: GetJobStatus
    review_speaker_mappings: ReviewSpeakerMappings


@dataclass(frozen=True, slots=True)
class TranscriptUseCases:
    preview_markdown: PreviewTranscriptMarkdown
    export_markdown: ExportTranscriptMarkdown


@dataclass(frozen=True, slots=True)
class RecapUseCases:
    generate: GenerateRecap
    preview_markdown: PreviewRecapMarkdown
    export_markdown: ExportRecapMarkdown


@dataclass(frozen=True, slots=True)
class MediaUseCases:
    inspect_metadata: InspectAudioMetadata
    inspect_local_file: InspectLocalAudioFile


@dataclass(frozen=True, slots=True)
class ApplicationUseCases:
    campaigns: CampaignUseCases
    participants: ParticipantUseCases
    samples: SampleUseCases
    recordings: RecordingUseCases
    jobs: JobUseCases
    transcripts: TranscriptUseCases
    recaps: RecapUseCases
    media: MediaUseCases
    settings: SettingsService | None = None


__all__ = [
    "ApplicationUseCases",
    "CampaignUseCases",
    "JobUseCases",
    "MediaUseCases",
    "ParticipantUseCases",
    "RecapUseCases",
    "RecordingUseCases",
    "SampleUseCases",
    "SettingsService",
    "TranscriptUseCases",
]
