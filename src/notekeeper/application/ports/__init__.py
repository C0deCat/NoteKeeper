"""Ports used by the application layer."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from notekeeper.application.results import (
    CampaignFolderSnapshot,
    PreparedAudioResult,
    ProgressEvent,
    RecapGenerationContext,
    SpeakerMappingRecord,
    TranscriptChunk,
    RunProcessingJobResult,
)
from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrack,
    AudioTrackId,
    Campaign,
    CampaignId,
    JobStatus,
    Participant,
    ParticipantId,
    ProcessingJob,
    ProcessingJobId,
    ProcessingStage,
    Recap,
    RecapChunk,
    RecapId,
    SpeakerMapping,
    Transcript,
    TranscriptId,
    VoiceSample,
    VoiceSampleId,
)

ProgressEventListener = Callable[[ProgressEvent], None]
Unsubscribe = Callable[[], None]


class ProgressEventPublisher(Protocol):
    def publish(self, event: ProgressEvent) -> None: ...


class ProgressEventStream(Protocol):
    def subscribe(
        self,
        operation_id: str,
        listener: ProgressEventListener,
        *,
        replay_latest: bool = True,
    ) -> Unsubscribe: ...

    def latest(self, operation_id: str) -> ProgressEvent | None: ...


class ProgressEventHub(ProgressEventPublisher, ProgressEventStream, Protocol):
    pass


class ProgressTracker(Protocol):
    def start_stage(
        self,
        stage: ProcessingStage,
        *,
        timing_available: bool,
    ) -> None: ...

    def update_fraction(self, fraction: float) -> None: ...

    def complete_stage(self) -> None: ...

    def complete(self) -> None: ...

    def pause(self) -> None: ...

    def fail(self) -> None: ...

    def cancel(self) -> None: ...

    def close(self) -> None: ...


class ProgressTrackerFactory(Protocol):
    def create(
        self,
        operation_id: str,
        stages: tuple[ProcessingStage, ...],
    ) -> ProgressTracker: ...


class CampaignRepository(Protocol):
    def get(self, campaign_id: CampaignId) -> Campaign | None: ...

    def list(self) -> tuple[Campaign, ...]: ...

    def save(self, campaign: Campaign) -> None: ...

    def delete(self, campaign_id: CampaignId) -> None: ...


class ParticipantRepository(Protocol):
    def get(self, participant_id: ParticipantId) -> Participant | None: ...

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[Participant, ...]: ...

    def save(self, participant: Participant) -> None: ...

    def delete(self, participant_id: ParticipantId) -> None: ...


class VoiceSampleRepository(Protocol):
    def get(self, voice_sample_id: VoiceSampleId) -> VoiceSample | None: ...

    def get_by_artifact_uri(
        self,
        campaign_id: CampaignId,
        artifact_uri: str,
    ) -> VoiceSample | None: ...

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[VoiceSample, ...]: ...

    def list_for_participant(
        self,
        participant_id: ParticipantId,
    ) -> tuple[VoiceSample, ...]: ...

    def save(self, voice_sample: VoiceSample) -> None: ...

    def delete(self, voice_sample_id: VoiceSampleId) -> None: ...


class AudioTrackRepository(Protocol):
    def get(self, audio_track_id: AudioTrackId) -> AudioTrack | None: ...

    def get_by_artifact_uri(
        self,
        campaign_id: CampaignId,
        artifact_uri: str,
    ) -> AudioTrack | None: ...

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[AudioTrack, ...]: ...

    def save(self, audio_track: AudioTrack) -> None: ...

    def delete(self, audio_track_id: AudioTrackId) -> None: ...


class TranscriptRepository(Protocol):
    def get(self, transcript_id: TranscriptId) -> Transcript | None: ...

    def list_for_audio_track(self, audio_track_id: AudioTrackId) -> tuple[Transcript, ...]: ...

    def save(self, transcript: Transcript) -> None: ...

    def delete(self, transcript_id: TranscriptId) -> None: ...


class RecapRepository(Protocol):
    def get(self, recap_id: RecapId) -> Recap | None: ...

    def list_for_transcript(self, transcript_id: TranscriptId) -> tuple[Recap, ...]: ...

    def save(self, recap: Recap) -> None: ...

    def delete(self, recap_id: RecapId) -> None: ...


class JobRepository(Protocol):
    def get(self, job_id: ProcessingJobId) -> ProcessingJob | None: ...

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[ProcessingJob, ...]: ...

    def list_for_audio_track(
        self,
        audio_track_id: AudioTrackId,
    ) -> tuple[ProcessingJob, ...]: ...

    def save(self, job: ProcessingJob) -> None: ...

    def save_if_status(
        self,
        job: ProcessingJob,
        expected_status: JobStatus,
    ) -> bool: ...

    def delete(self, job_id: ProcessingJobId) -> None: ...


class JobCleaner(Protocol):
    def clean(
        self,
        campaign_id: CampaignId,
        jobs: tuple[ProcessingJob, ...],
    ) -> tuple[ProcessingJobId, ...]: ...


FailedJobCleaner = JobCleaner


class JobExecutionController(Protocol):
    def cancel(self, job_id: ProcessingJobId) -> None: ...


class JobProcessExecutor(JobExecutionController, Protocol):
    def execute(self, job_id: ProcessingJobId) -> RunProcessingJobResult: ...


class AudioMetadataReader(Protocol):
    def read(self, artifact: ArtifactRef) -> AudioMetadata: ...


class AudioProcessor(Protocol):
    def prepare_session_audio(
        self,
        audio_track: AudioTrack,
        voice_samples: tuple[VoiceSample, ...],
        *,
        job_id: ProcessingJobId,
        progress: ProgressTracker | None = None,
    ) -> PreparedAudioResult: ...


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


class SpeakerMappingRepository(Protocol):
    def save_many(self, records: tuple[SpeakerMappingRecord, ...]) -> None: ...

    def list_for_job(
        self,
        job_id: ProcessingJobId,
    ) -> tuple[SpeakerMappingRecord, ...]: ...

    def list_for_transcript(
        self,
        transcript_id: TranscriptId,
    ) -> tuple[SpeakerMappingRecord, ...]: ...


class Tokenizer(Protocol):
    def split_transcript(
        self,
        transcript: Transcript,
        *,
        target_token_count: int,
    ) -> tuple[TranscriptChunk, ...]: ...


class RecapGenerator(Protocol):
    def generate_chunk(
        self,
        chunk: TranscriptChunk,
        *,
        context: RecapGenerationContext,
    ) -> str: ...

    def combine_chunks(
        self,
        chunks: tuple[RecapChunk, ...],
        *,
        context: RecapGenerationContext,
    ) -> str: ...


class ArtifactStorage(Protocol):
    def save_text(
        self,
        *,
        suggested_name: str,
        content: str,
        media_type: str,
    ) -> ArtifactRef: ...


class CampaignArtifactStorage(ArtifactStorage, Protocol):
    def ensure_campaign_layout(self, campaign_id: CampaignId) -> None: ...

    def delete_campaign(self, campaign_id: CampaignId) -> None: ...

    def save_campaign_text(
        self,
        *,
        campaign_id: CampaignId,
        folder: str,
        suggested_name: str,
        content: str,
        media_type: str,
    ) -> ArtifactRef: ...


class PreparedAudioManifestStore(Protocol):
    def manifest_uri_for_job(
        self,
        *,
        campaign_id: CampaignId,
        job_id: ProcessingJobId,
    ) -> str: ...

    def save(
        self,
        *,
        campaign_id: CampaignId,
        job_id: ProcessingJobId,
        payload: dict[str, Any],
    ) -> ArtifactRef: ...

    def read(self, artifact: ArtifactRef) -> dict[str, Any]: ...

    def read_for_job(
        self,
        *,
        campaign_id: CampaignId,
        job_id: ProcessingJobId,
    ) -> dict[str, Any]: ...


class CampaignFolderScanner(Protocol):
    def scan(self, campaign_id: CampaignId) -> CampaignFolderSnapshot: ...


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
    "CampaignArtifactStorage",
    "CampaignFolderScanner",
    "CampaignRepository",
    "Clock",
    "FailedJobCleaner",
    "JobCleaner",
    "JobExecutionController",
    "JobProcessExecutor",
    "IdGenerator",
    "JobRepository",
    "ParticipantRepository",
    "PreparedAudioManifestStore",
    "ProgressEventListener",
    "ProgressEventHub",
    "ProgressEventPublisher",
    "ProgressEventStream",
    "ProgressTracker",
    "ProgressTrackerFactory",
    "RecapGenerator",
    "RecapRepository",
    "SpeakerIdentifier",
    "SpeakerMappingRepository",
    "Tokenizer",
    "Transcriber",
    "TranscriptRepository",
    "Unsubscribe",
    "VoiceSampleRepository",
]
