"""Application command DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateCampaignCommand:
    name: str


@dataclass(frozen=True, slots=True)
class GetCampaignCommand:
    campaign_id: str


@dataclass(frozen=True, slots=True)
class ListCampaignsCommand:
    pass


@dataclass(frozen=True, slots=True)
class UpdateCampaignCommand:
    campaign_id: str
    name: str


@dataclass(frozen=True, slots=True)
class DeleteCampaignCommand:
    campaign_id: str
    delete_files: bool = False


@dataclass(frozen=True, slots=True)
class AddParticipantToCampaignCommand:
    campaign_id: str
    display_name: str


@dataclass(frozen=True, slots=True)
class ListParticipantsCommand:
    campaign_id: str


@dataclass(frozen=True, slots=True)
class UpdateParticipantCommand:
    campaign_id: str
    participant_id: str
    display_name: str


@dataclass(frozen=True, slots=True)
class DeleteParticipantCommand:
    campaign_id: str
    participant_id: str


@dataclass(frozen=True, slots=True)
class AddVoiceSampleCommand:
    campaign_id: str
    participant_id: str
    artifact_uri: str
    artifact_kind: str = "file"
    recorded_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ListVoiceSamplesCommand:
    campaign_id: str
    participant_id: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateVoiceSampleCommand:
    campaign_id: str
    voice_sample_id: str
    artifact_uri: str
    artifact_kind: str = "file"
    recorded_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DeleteVoiceSampleCommand:
    campaign_id: str
    voice_sample_id: str


@dataclass(frozen=True, slots=True)
class RegisterAudioTrackCommand:
    campaign_id: str
    artifact_uri: str
    artifact_kind: str = "file"
    title: str | None = None


@dataclass(frozen=True, slots=True)
class ListAudioTracksCommand:
    campaign_id: str


@dataclass(frozen=True, slots=True)
class ListJobsForCampaignCommand:
    campaign_id: str


@dataclass(frozen=True, slots=True)
class UpdateAudioTrackCommand:
    campaign_id: str
    audio_track_id: str
    artifact_uri: str
    artifact_kind: str = "file"
    title: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteAudioTrackCommand:
    campaign_id: str
    audio_track_id: str


@dataclass(frozen=True, slots=True)
class CreateProcessingJobForAudioTrackCommand:
    audio_track_id: str


@dataclass(frozen=True, slots=True)
class SubmitRecordingForProcessingCommand:
    campaign_id: str
    artifact_uri: str
    artifact_kind: str = "file"
    title: str | None = None


@dataclass(frozen=True, slots=True)
class RunProcessingJobCommand:
    job_id: str


@dataclass(frozen=True, slots=True)
class RestartFailedProcessingJobCommand:
    job_id: str


@dataclass(frozen=True, slots=True)
class ManualSpeakerMappingCommand:
    anonymous_label: str
    participant_id: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class ReviewSpeakerMappingsCommand:
    job_id: str
    mappings: tuple[ManualSpeakerMappingCommand, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "mappings", tuple(self.mappings))


@dataclass(frozen=True, slots=True)
class GenerateRecapCommand:
    transcript_id: str


@dataclass(frozen=True, slots=True)
class ExportTranscriptMarkdownCommand:
    transcript_id: str


@dataclass(frozen=True, slots=True)
class ExportRecapMarkdownCommand:
    recap_id: str


@dataclass(frozen=True, slots=True)
class GetJobStatusCommand:
    job_id: str


@dataclass(frozen=True, slots=True)
class InspectAudioMetadataCommand:
    artifact_uri: str
    artifact_kind: str = "file"


@dataclass(frozen=True, slots=True)
class PreviewTranscriptMarkdownCommand:
    transcript_id: str


@dataclass(frozen=True, slots=True)
class PreviewRecapMarkdownCommand:
    recap_id: str


@dataclass(frozen=True, slots=True)
class SyncCampaignFolderCommand:
    campaign_id: str


__all__ = [
    "AddParticipantToCampaignCommand",
    "AddVoiceSampleCommand",
    "CreateCampaignCommand",
    "CreateProcessingJobForAudioTrackCommand",
    "DeleteAudioTrackCommand",
    "DeleteCampaignCommand",
    "DeleteParticipantCommand",
    "DeleteVoiceSampleCommand",
    "ExportRecapMarkdownCommand",
    "ExportTranscriptMarkdownCommand",
    "GenerateRecapCommand",
    "GetCampaignCommand",
    "GetJobStatusCommand",
    "ListAudioTracksCommand",
    "ListCampaignsCommand",
    "ListJobsForCampaignCommand",
    "ListParticipantsCommand",
    "ListVoiceSamplesCommand",
    "ManualSpeakerMappingCommand",
    "InspectAudioMetadataCommand",
    "PreviewRecapMarkdownCommand",
    "PreviewTranscriptMarkdownCommand",
    "RegisterAudioTrackCommand",
    "ReviewSpeakerMappingsCommand",
    "RestartFailedProcessingJobCommand",
    "RunProcessingJobCommand",
    "SubmitRecordingForProcessingCommand",
    "SyncCampaignFolderCommand",
    "UpdateAudioTrackCommand",
    "UpdateCampaignCommand",
    "UpdateParticipantCommand",
    "UpdateVoiceSampleCommand",
]
