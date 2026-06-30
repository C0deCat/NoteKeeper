"""Ports used by the application layer."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from notekeeper.application.results import TranscriptChunk
from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrack,
    AudioTrackId,
    Campaign,
    CampaignId,
    ProcessingJob,
    ProcessingJobId,
    Recap,
    RecapChunk,
    RecapId,
    SpeakerMapping,
    Transcript,
    TranscriptId,
    VoiceSample,
)


class CampaignRepository(Protocol):
    def get(self, campaign_id: CampaignId) -> Campaign | None: ...

    def save(self, campaign: Campaign) -> None: ...


class AudioTrackRepository(Protocol):
    def get(self, audio_track_id: AudioTrackId) -> AudioTrack | None: ...

    def save(self, audio_track: AudioTrack) -> None: ...


class TranscriptRepository(Protocol):
    def get(self, transcript_id: TranscriptId) -> Transcript | None: ...

    def save(self, transcript: Transcript) -> None: ...


class RecapRepository(Protocol):
    def get(self, recap_id: RecapId) -> Recap | None: ...

    def save(self, recap: Recap) -> None: ...


class JobRepository(Protocol):
    def get(self, job_id: ProcessingJobId) -> ProcessingJob | None: ...

    def save(self, job: ProcessingJob) -> None: ...


class AudioMetadataReader(Protocol):
    def read(self, artifact: ArtifactRef) -> AudioMetadata: ...


class AudioProcessor(Protocol):
    def prepare_session_audio(
        self,
        audio_track: AudioTrack,
        voice_samples: tuple[VoiceSample, ...],
    ) -> ArtifactRef: ...


class Transcriber(Protocol):
    def transcribe(
        self,
        audio: ArtifactRef,
        *,
        transcript_id: TranscriptId,
        campaign_id: CampaignId,
        audio_track_id: AudioTrackId,
    ) -> Transcript: ...


class SpeakerIdentifier(Protocol):
    def identify(
        self,
        campaign: Campaign,
        transcript: Transcript,
    ) -> tuple[SpeakerMapping, ...]: ...


class Tokenizer(Protocol):
    def split_transcript(
        self,
        transcript: Transcript,
        *,
        target_token_count: int,
    ) -> tuple[TranscriptChunk, ...]: ...


class RecapGenerator(Protocol):
    def generate_chunk(self, chunk: TranscriptChunk) -> str: ...

    def combine_chunks(self, chunks: tuple[RecapChunk, ...]) -> str: ...


class ArtifactStorage(Protocol):
    def save_text(
        self,
        *,
        suggested_name: str,
        content: str,
        media_type: str,
    ) -> ArtifactRef: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    def campaign_id(self) -> str: ...

    def participant_id(self) -> str: ...

    def voice_sample_id(self) -> str: ...

    def audio_track_id(self) -> str: ...

    def processing_job_id(self) -> str: ...

    def transcript_id(self) -> str: ...

    def recap_id(self) -> str: ...


__all__ = [
    "ArtifactStorage",
    "AudioMetadataReader",
    "AudioProcessor",
    "AudioTrackRepository",
    "CampaignRepository",
    "Clock",
    "IdGenerator",
    "JobRepository",
    "RecapGenerator",
    "RecapRepository",
    "SpeakerIdentifier",
    "Tokenizer",
    "Transcriber",
    "TranscriptRepository",
]
