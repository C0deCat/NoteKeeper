"""Application result DTOs."""

from __future__ import annotations

from dataclasses import dataclass

from notekeeper.domain import (
    ArtifactRef,
    AudioTrack,
    Campaign,
    Participant,
    PipelineWarning,
    ProcessingJob,
    Recap,
    SpeakerMapping,
    TimeRange,
    Transcript,
    TranscriptSegment,
    VoiceSample,
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
class CreateCampaignResult:
    campaign: Campaign


@dataclass(frozen=True, slots=True)
class AddParticipantToCampaignResult:
    campaign: Campaign
    participant: Participant


@dataclass(frozen=True, slots=True)
class AddVoiceSampleResult:
    campaign: Campaign
    voice_sample: VoiceSample


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


__all__ = [
    "AddParticipantToCampaignResult",
    "AddVoiceSampleResult",
    "CreateCampaignResult",
    "ExportMarkdownResult",
    "GenerateRecapResult",
    "GetJobStatusResult",
    "ReviewSpeakerMappingsResult",
    "RunProcessingJobResult",
    "SubmitRecordingForProcessingResult",
    "TranscriptChunk",
]
