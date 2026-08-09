"""Ports used by audio and processing workflows."""

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol

from notekeeper.application.results import (
    NormalizedAudioResult,
    PreparedAudioResult,
    TranscriptChunk,
)
from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrack,
    AudioTrackId,
    Campaign,
    CampaignId,
    ProcessingJob,
    ProcessingJobId,
    SpeakerMapping,
    Transcript,
    TranscriptId,
    VoiceSample,
)

from .events import ProgressTracker


class JobCleaner(Protocol):
    def clean(
        self,
        campaign_id: CampaignId,
        jobs: tuple[ProcessingJob, ...],
    ) -> tuple[ProcessingJobId, ...]: ...


FailedJobCleaner = JobCleaner


class TransientAudioCleaner(Protocol):
    def clean(self, campaign_id: CampaignId, job_id: ProcessingJobId) -> None: ...

    def clean_stale(self) -> None: ...


class JobManager(Protocol):
    def enqueue(self, job_id: ProcessingJobId) -> None: ...

    def request_cancel(self, job_id: ProcessingJobId) -> None: ...


class CampaignMutationGuard(Protocol):
    def acquire(self, campaign_id: CampaignId) -> AbstractContextManager[None]: ...


class AudioMetadataReader(Protocol):
    def read(self, artifact: ArtifactRef) -> AudioMetadata: ...


class SourceAudioMetadataReader(Protocol):
    def read(self, source_path: Path) -> AudioMetadata: ...


class AudioProcessor(Protocol):
    def prepare_session_audio(
        self,
        audio_track: AudioTrack,
        voice_samples: tuple[VoiceSample, ...],
        *,
        job_id: ProcessingJobId,
        progress: ProgressTracker | None = None,
    ) -> PreparedAudioResult: ...


class AudioRecordingNormalizer(Protocol):
    def normalize_artifact(
        self,
        *,
        campaign_id: CampaignId,
        audio_track_id: AudioTrackId,
        source_artifact: ArtifactRef,
        source_metadata: AudioMetadata,
    ) -> NormalizedAudioResult: ...

    def normalize_source(
        self,
        *,
        campaign_id: CampaignId,
        audio_track_id: AudioTrackId,
        source_path: Path,
        source_metadata: AudioMetadata,
    ) -> NormalizedAudioResult: ...

    def find_for_source(
        self,
        *,
        campaign_id: CampaignId,
        source_artifact: ArtifactRef,
        source_metadata: AudioMetadata,
    ) -> NormalizedAudioResult | None: ...


class Transcriber(Protocol):
    def transcribe(
        self,
        audio: ArtifactRef,
        *,
        transcript_id: TranscriptId,
        campaign_id: CampaignId,
        audio_track_id: AudioTrackId,
        progress: ProgressTracker | None = None,
    ) -> Transcript: ...


class SpeakerIdentifier(Protocol):
    def identify(
        self,
        campaign: Campaign,
        transcript: Transcript,
        *,
        prepared_audio: PreparedAudioResult,
    ) -> tuple[SpeakerMapping, ...]: ...


class Tokenizer(Protocol):
    def split_transcript(
        self,
        transcript: Transcript,
        *,
        target_token_count: int,
    ) -> tuple[TranscriptChunk, ...]: ...

