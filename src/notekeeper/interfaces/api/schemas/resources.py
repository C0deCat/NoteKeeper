"""Workspace resource request and response DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from .common import ApiSchema


class CampaignRequest(ApiSchema):
    name: str = Field(min_length=1)


class CampaignPatchRequest(ApiSchema):
    name: str = Field(min_length=1)


class CampaignResponse(ApiSchema):
    campaign_id: str
    workspace_id: str
    name: str


class ParticipantRequest(ApiSchema):
    display_name: str = Field(min_length=1)


class ParticipantPatchRequest(ApiSchema):
    display_name: str = Field(min_length=1)


class ParticipantResponse(ApiSchema):
    participant_id: str
    campaign_id: str
    display_name: str


class AudioMetadataResponse(ApiSchema):
    duration_seconds: float
    sample_rate_hz: int | None = None
    channels: int | None = None
    codec: str | None = None
    format: str | None = None
    bitrate_bps: int | None = None
    file_size_bytes: int | None = None
    checksum: str | None = None


class VoiceSampleResponse(ApiSchema):
    sample_id: str
    campaign_id: str
    participant_id: str
    recorded_at: datetime | None = None
    metadata: AudioMetadataResponse


class RecordingResponse(ApiSchema):
    recording_id: str
    campaign_id: str
    title: str | None = None
    metadata: AudioMetadataResponse


class TimeRangeResponse(ApiSchema):
    start_seconds: float
    end_seconds: float


class WarningResponse(ApiSchema):
    kind: str
    message: str
    time_range: TimeRangeResponse | None = None
    speaker_label: str | None = None
    participant_id: str | None = None


class ProgressResponse(ApiSchema):
    operation_id: str
    kind: str
    stage_index: int
    stage_count: int
    timing_available: bool
    stage: str
    percent: float
    expected_duration: int
    current_duration: int
    remaining_duration: int


class JobResponse(ApiSchema):
    job_id: str
    campaign_id: str
    recording_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    transcript_id: str | None = None
    recap_id: str | None = None
    warnings: list[WarningResponse]
    error_message: str | None = None
    progress: ProgressResponse | None = None


class RecordingSubmissionResponse(ApiSchema):
    recording: RecordingResponse
    job: JobResponse


class RestartJobResponse(ApiSchema):
    source_job_id: str
    job: JobResponse


class SpeakerReviewDecision(ApiSchema):
    anonymous_label: str = Field(min_length=1)
    participant_id: str | None = None
    named_label: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_target(self) -> "SpeakerReviewDecision":
        if (self.participant_id is None) == (self.named_label is None):
            raise ValueError(
                "exactly one of participant_id or named_label is required"
            )
        return self


class SpeakerReviewRequest(ApiSchema):
    mappings: list[SpeakerReviewDecision] = Field(min_length=1)


class MarkdownResponse(ApiSchema):
    id: str
    markdown: str


__all__ = [
    "AudioMetadataResponse",
    "CampaignPatchRequest",
    "CampaignRequest",
    "CampaignResponse",
    "JobResponse",
    "MarkdownResponse",
    "ParticipantPatchRequest",
    "ParticipantRequest",
    "ParticipantResponse",
    "ProgressResponse",
    "RecordingResponse",
    "RecordingSubmissionResponse",
    "RestartJobResponse",
    "SpeakerReviewDecision",
    "SpeakerReviewRequest",
    "TimeRangeResponse",
    "VoiceSampleResponse",
    "WarningResponse",
]
