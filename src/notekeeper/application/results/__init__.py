"""Application result DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from notekeeper.domain import (
    ArtifactRef,
    AudioTrack,
    Campaign,
    Participant,
    ParticipantId,
    PipelineWarning,
    ProcessingJob,
    ProcessingJobId,
    Recap,
    SpeakerMapping,
    TimeRange,
    Transcript,
    TranscriptSegment,
    TranscriptId,
    VoiceSample,
    VoiceSampleId,
)


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


@dataclass(frozen=True, slots=True)
class ListAudioTracksResult:
    audio_tracks: tuple[AudioTrack, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "audio_tracks", tuple(self.audio_tracks))


@dataclass(frozen=True, slots=True)
class UpdateAudioTrackResult:
    campaign: Campaign
    audio_track: AudioTrack


@dataclass(frozen=True, slots=True)
class DeleteAudioTrackResult:
    campaign: Campaign
    audio_track_id: str


@dataclass(frozen=True, slots=True)
class SubmitRecordingForProcessingResult:
    campaign: Campaign
    audio_track: AudioTrack
    job: ProcessingJob


@dataclass(frozen=True, slots=True)
class RunProcessingJobResult:
    job: ProcessingJob
    transcript: Transcript | None
    recap: Recap | None
    warnings: tuple[PipelineWarning, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "warnings", tuple(self.warnings))


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
    recap: Recap


@dataclass(frozen=True, slots=True)
class ExportMarkdownResult:
    artifact: ArtifactRef


@dataclass(frozen=True, slots=True)
class GetJobStatusResult:
    job: ProcessingJob


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


__all__ = [
    "AddParticipantToCampaignResult",
    "AddVoiceSampleResult",
    "CampaignFolderSnapshot",
    "CreateCampaignResult",
    "DeleteAudioTrackResult",
    "DeleteCampaignResult",
    "DeleteParticipantResult",
    "DeleteVoiceSampleResult",
    "ExportMarkdownResult",
    "GenerateRecapResult",
    "GetCampaignResult",
    "GetJobStatusResult",
    "ListAudioTracksResult",
    "ListCampaignsResult",
    "ListParticipantsResult",
    "ListVoiceSamplesResult",
    "PreparedAudioResult",
    "PreparedVoiceSampleRange",
    "RegisterAudioTrackResult",
    "ReviewSpeakerMappingsResult",
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
