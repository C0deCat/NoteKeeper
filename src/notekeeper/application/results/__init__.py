"""Application result DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from notekeeper.domain import (
    ArtifactRef,
    AudioTrack,
    AudioMetadata,
    Campaign,
    CampaignId,
    Participant,
    ParticipantId,
    PipelineWarning,
    ProgressBar,
    ProcessingJob,
    ProcessingJobId,
    Recap,
    RecapId,
    SpeakerMapping,
    TimeRange,
    Transcript,
    TranscriptSegment,
    TranscriptId,
    VoiceSample,
    VoiceSampleId,
)


class ProgressEventKind(str, Enum):
    STARTED = "started"
    UPDATED = "updated"
    STAGE_COMPLETED = "stage_completed"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"
    CANCELED = "canceled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            self.COMPLETED,
            self.PAUSED,
            self.FAILED,
            self.CANCELED,
        }


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    operation_id: str
    stage_index: int
    stage_count: int
    timing_available: bool
    kind: ProgressEventKind
    progress: ProgressBar

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or not self.operation_id.strip():
            raise ValueError("operation_id must not be empty")
        if isinstance(self.stage_count, bool) or not isinstance(
            self.stage_count,
            int,
        ) or self.stage_count < 1:
            raise ValueError("stage_count must be positive")
        if isinstance(self.stage_index, bool) or not isinstance(
            self.stage_index,
            int,
        ) or not 1 <= self.stage_index <= self.stage_count:
            raise ValueError("stage_index must be within stage_count")


@dataclass(frozen=True, slots=True)
class TranscriptChunk:
    text: str
    segments: tuple[TranscriptSegment, ...] = ()
    time_range: TimeRange | None = None
    source_segment_indexes: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "segments", tuple(self.segments))
        object.__setattr__(
            self,
            "source_segment_indexes",
            tuple(self.source_segment_indexes),
        )


@dataclass(frozen=True, slots=True)
class RecapGenerationContext:
    campaign_id: CampaignId
    transcript_id: TranscriptId
    recap_id: RecapId
    job_id: ProcessingJobId | None = None
    chunk_index: int | None = None


@dataclass(frozen=True, slots=True)
class PreparedVoiceSampleRange:
    source_artifact: ArtifactRef
    voice_sample_id: VoiceSampleId
    participant_id: ParticipantId
    time_range: TimeRange


@dataclass(frozen=True, slots=True)
class PreparedAudioResult:
    audio_artifact: ArtifactRef
    manifest_artifact: ArtifactRef
    source_audio_artifact: ArtifactRef
    session_time_range: TimeRange
    voice_sample_ranges: tuple[PreparedVoiceSampleRange, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "voice_sample_ranges",
            tuple(self.voice_sample_ranges),
        )


@dataclass(frozen=True, slots=True)
class NormalizedAudioResult:
    audio_track_id: AudioTrackId
    audio_artifact: ArtifactRef
    manifest_artifact: ArtifactRef
    metadata: AudioMetadata
    source_checksum: str | None
    source_size_bytes: int
    normalized_size_bytes: int

    @property
    def bytes_freed(self) -> int:
        return max(0, self.source_size_bytes - self.normalized_size_bytes)


@dataclass(frozen=True, slots=True)
class SpeakerMappingRecord:
    job_id: ProcessingJobId
    transcript_id: TranscriptId
    mapping: SpeakerMapping
    diagnostics: dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", dict(self.diagnostics))


@dataclass(frozen=True, slots=True)
class CreateCampaignResult:
    campaign: Campaign


@dataclass(frozen=True, slots=True)
class GetCampaignResult:
    campaign: Campaign


@dataclass(frozen=True, slots=True)
class ListCampaignsResult:
    campaigns: tuple[Campaign, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "campaigns", tuple(self.campaigns))


@dataclass(frozen=True, slots=True)
class UpdateCampaignResult:
    campaign: Campaign


@dataclass(frozen=True, slots=True)
class DeleteCampaignResult:
    campaign_id: str


@dataclass(frozen=True, slots=True)
class AddParticipantToCampaignResult:
    campaign: Campaign
    participant: Participant


@dataclass(frozen=True, slots=True)
class ListParticipantsResult:
    participants: tuple[Participant, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "participants", tuple(self.participants))


@dataclass(frozen=True, slots=True)
class UpdateParticipantResult:
    campaign: Campaign
    participant: Participant


@dataclass(frozen=True, slots=True)
class DeleteParticipantResult:
    campaign: Campaign
    participant_id: str


@dataclass(frozen=True, slots=True)
class AddVoiceSampleResult:
    campaign: Campaign
    voice_sample: VoiceSample


@dataclass(frozen=True, slots=True)
class ListVoiceSamplesResult:
    voice_samples: tuple[VoiceSample, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "voice_samples", tuple(self.voice_samples))


@dataclass(frozen=True, slots=True)
class UpdateVoiceSampleResult:
    campaign: Campaign
    voice_sample: VoiceSample


@dataclass(frozen=True, slots=True)
class DeleteVoiceSampleResult:
    campaign: Campaign
    voice_sample_id: str


@dataclass(frozen=True, slots=True)
class RegisterAudioTrackResult:
    campaign: Campaign
    audio_track: AudioTrack
    normalized_count: int = 0
    bytes_freed: int = 0
    cleanup_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "cleanup_warnings", tuple(self.cleanup_warnings))


@dataclass(frozen=True, slots=True)
class ListAudioTracksResult:
    audio_tracks: tuple[AudioTrack, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "audio_tracks", tuple(self.audio_tracks))


@dataclass(frozen=True, slots=True)
class ListJobsForCampaignResult:
    jobs: tuple[ProcessingJob, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "jobs", tuple(self.jobs))


@dataclass(frozen=True, slots=True)
class ClearFailedJobsForCampaignResult:
    deleted_job_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "deleted_job_ids", tuple(self.deleted_job_ids))


@dataclass(frozen=True, slots=True)
class DeleteProcessingJobResult:
    job_id: str


@dataclass(frozen=True, slots=True)
class CancelProcessingJobResult:
    job: ProcessingJob


@dataclass(frozen=True, slots=True)
class UpdateAudioTrackResult:
    campaign: Campaign
    audio_track: AudioTrack
    normalized_count: int = 0
    bytes_freed: int = 0
    cleanup_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "cleanup_warnings", tuple(self.cleanup_warnings))


@dataclass(frozen=True, slots=True)
class DeleteAudioTrackResult:
    campaign: Campaign
    audio_track_id: str


@dataclass(frozen=True, slots=True)
class CreateProcessingJobForAudioTrackResult:
    campaign: Campaign
    audio_track: AudioTrack
    job: ProcessingJob


@dataclass(frozen=True, slots=True)
class SubmitRecordingForProcessingResult:
    campaign: Campaign
    audio_track: AudioTrack
    job: ProcessingJob
    normalized_count: int = 0
    bytes_freed: int = 0
    cleanup_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "cleanup_warnings", tuple(self.cleanup_warnings))


@dataclass(frozen=True, slots=True)
class RunProcessingJobResult:
    job: ProcessingJob
    transcript: Transcript | None
    recap: Recap | None
    warnings: tuple[PipelineWarning, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True, slots=True)
class RestartProcessingJobResult:
    campaign: Campaign
    audio_track: AudioTrack
    source_job: ProcessingJob
    job: ProcessingJob


RestartFailedProcessingJobResult = RestartProcessingJobResult


@dataclass(frozen=True, slots=True)
class ReviewSpeakerMappingsResult:
    job: ProcessingJob
    transcript: Transcript
    recap: Recap | None
    warnings: tuple[PipelineWarning, ...] = ()
    applied_mappings: tuple[SpeakerMapping, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "applied_mappings", tuple(self.applied_mappings))


@dataclass(frozen=True, slots=True)
class GenerateRecapResult:
    job: ProcessingJob
    recap: Recap


@dataclass(frozen=True, slots=True)
class ExportMarkdownResult:
    artifact: ArtifactRef


@dataclass(frozen=True, slots=True)
class GetJobStatusResult:
    job: ProcessingJob


@dataclass(frozen=True, slots=True)
class InspectAudioMetadataResult:
    artifact: ArtifactRef
    metadata: AudioMetadata


@dataclass(frozen=True, slots=True)
class InspectLocalAudioFileResult:
    source_path: str
    metadata: AudioMetadata


@dataclass(frozen=True, slots=True)
class MarkdownPreviewResult:
    markdown: str


@dataclass(frozen=True, slots=True)
class ScannedVoiceSampleArtifact:
    player_name: str
    artifact: ArtifactRef


@dataclass(frozen=True, slots=True)
class ScannedAudioTrackArtifact:
    artifact: ArtifactRef
    title: str | None = None


@dataclass(frozen=True, slots=True)
class CampaignFolderSnapshot:
    campaign_id: str
    voice_samples: tuple[ScannedVoiceSampleArtifact, ...] = ()
    audio_tracks: tuple[ScannedAudioTrackArtifact, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "voice_samples", tuple(self.voice_samples))
        object.__setattr__(self, "audio_tracks", tuple(self.audio_tracks))


@dataclass(frozen=True, slots=True)
class SyncCampaignFolderResult:
    campaign: Campaign
    participants_created: int = 0
    voice_samples_added: int = 0
    voice_samples_updated: int = 0
    voice_samples_deleted: int = 0
    audio_tracks_added: int = 0
    audio_tracks_updated: int = 0
    audio_tracks_deleted: int = 0
    pending_jobs_deleted: int = 0
    audio_tracks_normalized: int = 0
    bytes_freed: int = 0
    cleanup_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "cleanup_warnings", tuple(self.cleanup_warnings))


__all__ = [
    "AddParticipantToCampaignResult",
    "AddVoiceSampleResult",
    "CancelProcessingJobResult",
    "CampaignFolderSnapshot",
    "ClearFailedJobsForCampaignResult",
    "CreateCampaignResult",
    "CreateProcessingJobForAudioTrackResult",
    "DeleteAudioTrackResult",
    "DeleteCampaignResult",
    "DeleteParticipantResult",
    "DeleteProcessingJobResult",
    "DeleteVoiceSampleResult",
    "ExportMarkdownResult",
    "GenerateRecapResult",
    "GetCampaignResult",
    "GetJobStatusResult",
    "InspectAudioMetadataResult",
    "InspectLocalAudioFileResult",
    "ListAudioTracksResult",
    "ListCampaignsResult",
    "ListJobsForCampaignResult",
    "ListParticipantsResult",
    "ListVoiceSamplesResult",
    "MarkdownPreviewResult",
    "NormalizedAudioResult",
    "PreparedAudioResult",
    "PreparedVoiceSampleRange",
    "ProgressEvent",
    "ProgressEventKind",
    "RecapGenerationContext",
    "RegisterAudioTrackResult",
    "ReviewSpeakerMappingsResult",
    "RestartFailedProcessingJobResult",
    "RestartProcessingJobResult",
    "RunProcessingJobResult",
    "ScannedAudioTrackArtifact",
    "ScannedVoiceSampleArtifact",
    "SpeakerMappingRecord",
    "SubmitRecordingForProcessingResult",
    "SyncCampaignFolderResult",
    "TranscriptChunk",
    "UpdateAudioTrackResult",
    "UpdateCampaignResult",
    "UpdateParticipantResult",
    "UpdateVoiceSampleResult",
]
