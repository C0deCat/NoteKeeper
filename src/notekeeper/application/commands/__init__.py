"""Application command DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateCampaignCommand:
    name: str


@dataclass(frozen=True, slots=True)
class AddParticipantToCampaignCommand:
    campaign_id: str
    display_name: str


@dataclass(frozen=True, slots=True)
class AddVoiceSampleCommand:
    campaign_id: str
    participant_id: str
    artifact_uri: str
    artifact_kind: str = "file"
    recorded_at: datetime | None = None


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


__all__ = [
    "AddParticipantToCampaignCommand",
    "AddVoiceSampleCommand",
    "CreateCampaignCommand",
    "ExportRecapMarkdownCommand",
    "ExportTranscriptMarkdownCommand",
    "GenerateRecapCommand",
    "GetJobStatusCommand",
    "ManualSpeakerMappingCommand",
    "ReviewSpeakerMappingsCommand",
    "RunProcessingJobCommand",
    "SubmitRecordingForProcessingCommand",
]
