from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from notekeeper.application import (
    AddParticipantToCampaign,
    AddParticipantToCampaignCommand,
    AddVoiceSample,
    AddVoiceSampleCommand,
    CampaignFolderSnapshot,
    ClearFailedJobsForCampaign,
    ClearFailedJobsForCampaignCommand,
    CreateCampaign,
    CreateCampaignCommand,
    CreateProcessingJobForAudioTrack,
    CreateProcessingJobForAudioTrackCommand,
    DeleteCampaign,
    DeleteCampaignCommand,
    ExportRecapMarkdown,
    ExportRecapMarkdownCommand,
    ExportTranscriptMarkdown,
    ExportTranscriptMarkdownCommand,
    GenerateRecap,
    GenerateRecapCommand,
    GetRecapGuidances,
    GetRecapGuidancesCommand,
    GetJobStatus,
    GetJobStatusCommand,
    InspectAudioMetadata,
    InspectAudioMetadataCommand,
    InspectLocalAudioFile,
    InspectLocalAudioFileCommand,
    InvalidOperationError,
    ListJobsForCampaign,
    ListJobsForCampaignCommand,
    ManualSpeakerMappingCommand,
    NotFoundError,
    NormalizedAudioResult,
    PreviewRecapMarkdown,
    PreviewRecapMarkdownCommand,
    PreviewTranscriptMarkdown,
    PreviewTranscriptMarkdownCommand,
    PortExecutionError,
    PreparedAudioResult,
    RecapGenerationContext,
    RegisterAudioTrack,
    RegisterAudioTrackCommand,
    RestartFailedProcessingJob,
    RestartFailedProcessingJobCommand,
    ReviewSpeakerMappings,
    ReviewSpeakerMappingsCommand,
    RunProcessingJob,
    RunProcessingJobCommand,
    ScannedAudioTrackArtifact,
    ScannedVoiceSampleArtifact,
    SpeakerMappingRecord,
    SubmitRecordingForProcessing,
    SubmitRecordingForProcessingCommand,
    SyncCampaignFolder,
    SyncCampaignFolderCommand,
    TranscriptChunk,
    UpdateAudioTrack,
    UpdateAudioTrackCommand,
    UpdateRecapGuidances,
    UpdateRecapGuidancesCommand,
)
from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrack,
    AudioTrackId,
    Campaign,
    CampaignId,
    CampaignValidationError,
    JobStatus,
    Participant,
    ParticipantId,
    PipelineWarningKind,
    PipelineWarning,
    ProcessingJob,
    ProcessingJobId,
    Recap,
    RecapChunk,
    SpeakerLabel,
    SpeakerMapping,
    SpeakerMappingSource,
    SpeakerMappingStatus,
    TimeRange,
    Transcript,
    TranscriptSegment,
    TranscriptId,
    VoiceSample,
    VoiceSampleId,
    add_audio_track,
    add_participant,
    add_voice_sample,
)
from notekeeper.infrastructure import InfrastructureError


class InMemoryRepository:
    def __init__(self) -> None:
        self.items = {}
        self.saved_statuses: list[JobStatus] = []

    def get(self, item_id):
        return self.items.get(item_id)

    def list(self):
        return tuple(self.items.values())

    def save(self, item) -> None:
        self.items[item.id] = item
        if isinstance(item, ProcessingJob):
            self.saved_statuses.append(item.status)

    def save_if_status(self, item, expected_status) -> bool:
        current = self.items.get(item.id)
        if current is None or current.status is not expected_status:
            return False
        self.items[item.id] = item
        if isinstance(item, ProcessingJob):
            self.saved_statuses.append(item.status)
        return True

    def delete(self, item_id) -> None:
        self.items.pop(item_id, None)

    def get_by_artifact_uri(self, campaign_id, artifact_uri):
        for item in self.items.values():
            if item.campaign_id == campaign_id and item.artifact.uri == artifact_uri:
                return item
        return None

    def list_for_campaign(self, campaign_id):
        return tuple(
            item
            for item in self.items.values()
            if getattr(item, "campaign_id", None) == campaign_id
        )

    def list_for_participant(self, participant_id):
        return tuple(
            item
            for item in self.items.values()
            if getattr(item, "participant_id", None) == participant_id
        )

    def list_for_audio_track(self, audio_track_id):
        return tuple(
            item
            for item in self.items.values()
            if getattr(item, "audio_track_id", None) == audio_track_id
        )


class FakeIdGenerator:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def campaign_id(self) -> str:
        return self._next("campaign")

    def participant_id(self) -> str:
        return self._next("participant")

    def voice_sample_id(self) -> str:
        return self._next("voice-sample")

    def audio_track_id(self) -> str:
        return self._next("audio-track")

    def processing_job_id(self) -> str:
        return self._next("job")

    def transcript_id(self) -> str:
        return self._next("transcript")

    def recap_id(self) -> str:
        return self._next("recap")

    def _next(self, prefix: str) -> str:
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        return f"{prefix}-{self._counts[prefix]}"


class FakeClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 1, 1, 12, 0, 0)

    def now(self) -> datetime:
        current = self._now
        self._now += timedelta(seconds=1)
        return current


class FakeMetadataReader:
    def __init__(self) -> None:
        self.read_artifacts: list[ArtifactRef] = []

    def read(self, artifact: ArtifactRef) -> AudioMetadata:
        self.read_artifacts.append(artifact)
        return AudioMetadata(
            duration_seconds=12,
            sample_rate_hz=16000,
            channels=1,
            format="wav",
            checksum=f"checksum:{artifact.uri}",
        )


class FakeSourceMetadataReader:
    def __init__(self) -> None:
        self.read_paths: list[Path] = []

    def read(self, source_path: Path) -> AudioMetadata:
        self.read_paths.append(source_path)
        return AudioMetadata(
            duration_seconds=12,
            sample_rate_hz=16000,
            channels=1,
            format="wav",
            checksum=f"source-checksum:{source_path.name}",
        )


class FakeAudioProcessor:
    def __init__(self) -> None:
        self.calls: list[tuple[AudioTrack, tuple[VoiceSample, ...], ProcessingJobId]] = []
        self.error: PortExecutionError | None = None

    def prepare_session_audio(
        self,
        audio_track: AudioTrack,
        voice_samples: tuple[VoiceSample, ...],
        *,
        job_id: ProcessingJobId,
    ) -> PreparedAudioResult:
        self.calls.append((audio_track, voice_samples, job_id))
        if self.error is not None:
            raise self.error

        return PreparedAudioResult(
            audio_artifact=ArtifactRef(uri=f"prepared/{job_id}.wav"),
            manifest_artifact=ArtifactRef(uri=f"prepared/{job_id}.json"),
            source_audio_artifact=audio_track.artifact,
            session_time_range=TimeRange(
                start_seconds=0,
                end_seconds=audio_track.metadata.duration_seconds,
            ),
        )


class FakeAudioNormalizer:
    def __init__(self) -> None:
        self.artifact_calls = []
        self.source_calls = []
        self.recovered = None

    def normalize_artifact(
        self,
        *,
        campaign_id,
        audio_track_id,
        source_artifact,
        source_metadata,
    ) -> NormalizedAudioResult:
        self.artifact_calls.append(
            (campaign_id, audio_track_id, source_artifact, source_metadata),
        )
        return self._result(campaign_id, audio_track_id, source_metadata)

    def normalize_source(
        self,
        *,
        campaign_id,
        audio_track_id,
        source_path,
        source_metadata,
    ) -> NormalizedAudioResult:
        self.source_calls.append(
            (campaign_id, audio_track_id, source_path, source_metadata),
        )
        return self._result(campaign_id, audio_track_id, source_metadata)

    def find_for_source(self, **kwargs):
        return self.recovered

    @staticmethod
    def _result(campaign_id, audio_track_id, source_metadata):
        metadata = AudioMetadata(
            duration_seconds=source_metadata.duration_seconds,
            sample_rate_hz=16000,
            channels=1,
            codec="pcm_s16le",
            format="wav",
            file_size_bytes=25,
            checksum=f"normalized:{audio_track_id}",
        )
        return NormalizedAudioResult(
            audio_track_id=audio_track_id,
            audio_artifact=ArtifactRef(
                uri=f"{campaign_id}/records/normalized/{audio_track_id}.wav",
                checksum=metadata.checksum,
            ),
            manifest_artifact=ArtifactRef(
                uri=f"{campaign_id}/records/normalized/{audio_track_id}.json",
            ),
            metadata=metadata,
            source_checksum=source_metadata.checksum,
            source_size_bytes=100,
            normalized_size_bytes=25,
        )


class FakeTranscriber:
    def __init__(self) -> None:
        self.segments: tuple[TranscriptSegment, ...] = ()
        self.audio: ArtifactRef | None = None

    def transcribe(
        self,
        audio: ArtifactRef,
        *,
        transcript_id,
        campaign_id,
        audio_track_id,
    ) -> Transcript:
        self.audio = audio
        return Transcript(
            id=transcript_id,
            campaign_id=campaign_id,
            audio_track_id=audio_track_id,
            segments=self.segments,
        )


class FakeSpeakerIdentifier:
    def __init__(self) -> None:
        self.mappings: tuple[SpeakerMapping, ...] = ()
        self.calls: list[tuple[Campaign, Transcript, PreparedAudioResult]] = []

    def identify(
        self,
        campaign: Campaign,
        transcript: Transcript,
        *,
        prepared_audio: PreparedAudioResult,
    ) -> tuple[SpeakerMapping, ...]:
        self.calls.append((campaign, transcript, prepared_audio))
        return self.mappings


class FakeSpeakerMappingRepository:
    def __init__(self) -> None:
        self.records: list[SpeakerMappingRecord] = []

    def save_many(self, records: tuple[SpeakerMappingRecord, ...]) -> None:
        self.records.extend(records)

    def list_for_job(self, job_id) -> tuple[SpeakerMappingRecord, ...]:
        return tuple(record for record in self.records if record.job_id == job_id)

    def list_for_transcript(self, transcript_id) -> tuple[SpeakerMappingRecord, ...]:
        return tuple(
            record
            for record in self.records
            if record.transcript_id == transcript_id
        )


class FakeFailedJobCleaner:
    def __init__(self, job_repository: InMemoryRepository) -> None:
        self._job_repository = job_repository
        self.calls: list[tuple[CampaignId, tuple[ProcessingJob, ...]]] = []
        self.error: Exception | None = None

    def clean(
        self,
        campaign_id: CampaignId,
        jobs: tuple[ProcessingJob, ...],
    ) -> tuple[ProcessingJobId, ...]:
        self.calls.append((campaign_id, jobs))
        if self.error is not None:
            raise self.error
        for job in jobs:
            self._job_repository.delete(job.id)
        return tuple(job.id for job in jobs)


class FakeTransientAudioCleaner:
    def __init__(self) -> None:
        self.calls = []

    def clean(self, campaign_id, job_id) -> None:
        self.calls.append((campaign_id, job_id))

    def clean_stale(self) -> None:
        return None


class FakeTokenizer:
    def __init__(self) -> None:
        self.calls: list[tuple[Transcript, int]] = []

    def split_transcript(
        self,
        transcript: Transcript,
        *,
        target_token_count: int,
    ) -> tuple[TranscriptChunk, ...]:
        self.calls.append((transcript, target_token_count))
        segments = transcript.segments
        time_range = None
        if segments:
            time_range = TimeRange(
                segments[0].time_range.start_seconds,
                segments[-1].time_range.end_seconds,
            )

        return (
            TranscriptChunk(
                text="\n".join(segment.text for segment in segments),
                segments=segments,
                time_range=time_range,
                source_segment_indexes=tuple(segment.index for segment in segments),
            ),
        )


class FakeRecapGuidances:
    def __init__(self) -> None:
        self.chunk = "chunk guidance"
        self.combined = "combined guidance"
        self.chunk_reads: list[CampaignId] = []
        self.combined_reads: list[CampaignId] = []
        self.saved: list[tuple[CampaignId, str, str]] = []

    def get_chunk_recap_guidances(self, campaign_id: CampaignId) -> str:
        self.chunk_reads.append(campaign_id)
        return self.chunk

    def get_combined_recap_guidances(self, campaign_id: CampaignId) -> str:
        self.combined_reads.append(campaign_id)
        return self.combined

    def save_recap_guidances(
        self,
        campaign_id: CampaignId,
        *,
        chunk_recap_guidances: str,
        combined_recap_guidances: str,
    ) -> None:
        self.chunk = chunk_recap_guidances
        self.combined = combined_recap_guidances
        self.saved.append((campaign_id, self.chunk, self.combined))


class FakeRecapGenerator:
    def __init__(self) -> None:
        self.generated_chunks: list[TranscriptChunk] = []
        self.generated_contexts: list[RecapGenerationContext] = []
        self.generated_guidances: list[str] = []
        self.combined_chunks: tuple[RecapChunk, ...] = ()
        self.combined_contexts: list[RecapGenerationContext] = []
        self.combined_guidances: list[str] = []
        self.generate_error: PortExecutionError | None = None
        self.combine_error: PortExecutionError | None = None

    def generate_chunk(
        self,
        chunk: TranscriptChunk,
        *,
        guidance: str,
        context: RecapGenerationContext,
    ) -> str:
        self.generated_chunks.append(chunk)
        self.generated_contexts.append(context)
        self.generated_guidances.append(guidance)
        if self.generate_error is not None:
            raise self.generate_error

        return f"Chunk recap: {chunk.text or 'empty transcript'}"

    def combine_chunks(
        self,
        chunks: tuple[RecapChunk, ...],
        *,
        guidance: str,
        context: RecapGenerationContext,
    ) -> str:
        self.combined_chunks = chunks
        self.combined_contexts.append(context)
        self.combined_guidances.append(guidance)
        if self.combine_error is not None:
            raise self.combine_error

        chunk_text = "\n\n".join(chunk.markdown for chunk in chunks)
        return f"{chunk_text}\n\n## Summary\nDone"


class FakeArtifactStorage:
    def __init__(self) -> None:
        self.saved: dict[str, tuple[str, str, ArtifactRef]] = {}
        self.deleted_campaigns: list[CampaignId] = []
        self.delete_error: Exception | None = None
        self.imports: list[tuple[CampaignId, str, Path, str | None]] = []
        self.deleted_artifacts: list[ArtifactRef] = []
        self.artifact_delete_error: Exception | None = None
        self.missing_artifact_uris: set[str] = set()

    def ensure_campaign_layout(self, campaign_id: CampaignId) -> None:
        return None

    def delete_campaign(self, campaign_id: CampaignId) -> None:
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted_campaigns.append(campaign_id)

    def artifact_exists(self, artifact: ArtifactRef) -> bool:
        return artifact.uri not in self.missing_artifact_uris

    def delete_artifact(self, artifact: ArtifactRef) -> None:
        if self.artifact_delete_error is not None:
            raise self.artifact_delete_error
        self.deleted_artifacts.append(artifact)

    def save_text(
        self,
        *,
        suggested_name: str,
        content: str,
        media_type: str,
    ) -> ArtifactRef:
        artifact = ArtifactRef(uri=f"memory://{suggested_name}", kind="memory")
        self.saved[suggested_name] = (content, media_type, artifact)
        return artifact

    def import_file(
        self,
        *,
        campaign_id: CampaignId,
        folder: str,
        source_path: str | Path,
        player_name: str | None = None,
    ) -> ArtifactRef:
        path = Path(source_path)
        self.imports.append((campaign_id, folder, path, player_name))
        destination = (
            f"{campaign_id}/{folder}/{player_name}/{path.name}"
            if player_name is not None
            else f"{campaign_id}/{folder}/{path.name}"
        )
        return ArtifactRef(uri=destination)


class FakeCampaignFolderScanner:
    def __init__(self) -> None:
        self.snapshot = CampaignFolderSnapshot(campaign_id="campaign-1")

    def scan(self, campaign_id) -> CampaignFolderSnapshot:
        return self.snapshot


class Harness:
    def __init__(self) -> None:
        self.campaigns = InMemoryRepository()
        self.audio_tracks = InMemoryRepository()
        self.transcripts = InMemoryRepository()
        self.recaps = InMemoryRepository()
        self.jobs = InMemoryRepository()
        self.failed_job_cleaner = FakeFailedJobCleaner(self.jobs)
        self.transient_audio_cleaner = FakeTransientAudioCleaner()
        self.metadata_reader = FakeMetadataReader()
        self.source_metadata_reader = FakeSourceMetadataReader()
        self.audio_processor = FakeAudioProcessor()
        self.audio_normalizer = FakeAudioNormalizer()
        self.transcriber = FakeTranscriber()
        self.speaker_identifier = FakeSpeakerIdentifier()
        self.speaker_mappings = FakeSpeakerMappingRepository()
        self.tokenizer = FakeTokenizer()
        self.recap_guidances = FakeRecapGuidances()
        self.recap_generator = FakeRecapGenerator()
        self.artifact_storage = FakeArtifactStorage()
        self.folder_scanner = FakeCampaignFolderScanner()
        self.clock = FakeClock()
        self.ids = FakeIdGenerator()

    def ready_campaign(self, *names: str) -> Campaign:
        campaign = Campaign(id=CampaignId("campaign-1"), name="Curse of Strahd")
        for index, name in enumerate(names, start=1):
            participant = Participant(
                id=ParticipantId(f"participant-{index}"),
                campaign_id=campaign.id,
                display_name=name,
            )
            campaign = add_participant(campaign, participant)
            voice_sample = VoiceSample(
                id=VoiceSampleId(f"sample-{index}"),
                campaign_id=campaign.id,
                participant_id=participant.id,
                artifact=ArtifactRef(uri=f"samples/{name}.wav"),
                metadata=AudioMetadata(duration_seconds=12),
            )
            campaign = add_voice_sample(campaign, voice_sample)

        self.campaigns.save(campaign)
        return campaign

    def submit_use_case(self) -> SubmitRecordingForProcessing:
        return SubmitRecordingForProcessing(
            self.campaigns,
            self.audio_tracks,
            self.jobs,
            self.metadata_reader,
            self.source_metadata_reader,
            self.artifact_storage,
            self.clock,
            self.ids,
            audio_normalizer=self.audio_normalizer,
        )

    def create_job_for_audio_track_use_case(self) -> CreateProcessingJobForAudioTrack:
        return CreateProcessingJobForAudioTrack(
            self.campaigns,
            self.audio_tracks,
            self.jobs,
            self.clock,
            self.ids,
        )

    def run_use_case(self, *, clean_transient: bool = False) -> RunProcessingJob:
        return RunProcessingJob(
            self.campaigns,
            self.audio_tracks,
            self.transcripts,
            self.recaps,
            self.jobs,
            self.audio_processor,
            self.transcriber,
            self.speaker_identifier,
            self.speaker_mappings,
            self.tokenizer,
            self.recap_guidances,
            self.recap_generator,
            self.clock,
            self.ids,
            transient_audio_cleaner=(
                self.transient_audio_cleaner if clean_transient else None
            ),
        )

    def restart_use_case(self) -> RestartFailedProcessingJob:
        return RestartFailedProcessingJob(
            self.campaigns,
            self.audio_tracks,
            self.jobs,
            self.clock,
            self.ids,
        )

    def review_use_case(self) -> ReviewSpeakerMappings:
        return ReviewSpeakerMappings(
            self.campaigns,
            self.transcripts,
            self.recaps,
            self.jobs,
            self.speaker_mappings,
            self.tokenizer,
            self.recap_guidances,
            self.recap_generator,
            self.clock,
            self.ids,
        )

    def clear_failed_jobs_use_case(self) -> ClearFailedJobsForCampaign:
        return ClearFailedJobsForCampaign(
            self.campaigns,
            self.jobs,
            self.failed_job_cleaner,
        )

    def sync_use_case(self) -> SyncCampaignFolder:
        return SyncCampaignFolder(
            self.campaigns,
            self.jobs,
            self.folder_scanner,
            self.metadata_reader,
            self.ids,
            audio_normalizer=self.audio_normalizer,
            artifact_storage=self.artifact_storage,
        )


def test_campaign_use_cases_create_campaign_add_participant_and_voice_sample() -> None:
    harness = Harness()

    campaign = CreateCampaign(
        harness.campaigns,
        harness.ids,
        harness.recap_guidances,
    ).execute(
        CreateCampaignCommand(name="Storm King's Thunder"),
    ).campaign
    participant_result = AddParticipantToCampaign(
        harness.campaigns,
        harness.ids,
    ).execute(
        AddParticipantToCampaignCommand(
            campaign_id=campaign.id,
            display_name="Alice",
        ),
    )
    sample_result = AddVoiceSample(
        harness.campaigns,
        harness.metadata_reader,
        harness.source_metadata_reader,
        harness.artifact_storage,
        harness.ids,
    ).execute(
        AddVoiceSampleCommand(
            campaign_id=campaign.id,
            participant_id=participant_result.participant.id,
            artifact_uri="samples/alice.wav",
        ),
    )

    assert campaign.id == CampaignId("campaign-1")
    assert harness.recap_guidances.chunk_reads == [campaign.id]
    assert harness.recap_guidances.combined_reads == [campaign.id]
    assert participant_result.participant.id == ParticipantId("participant-1")
    assert sample_result.voice_sample.id == VoiceSampleId("voice-sample-1")
    assert sample_result.voice_sample.metadata.checksum == "checksum:samples/alice.wav"
    assert harness.campaigns.get(campaign.id).voice_samples == (
        sample_result.voice_sample,
    )


def test_get_and_partially_update_campaign_recap_guidances() -> None:
    harness = Harness()
    campaign = harness.ready_campaign()

    current = GetRecapGuidances(
        harness.campaigns,
        harness.recap_guidances,
    ).execute(GetRecapGuidancesCommand(campaign_id=str(campaign.id)))
    updated = UpdateRecapGuidances(
        harness.campaigns,
        harness.recap_guidances,
    ).execute(
        UpdateRecapGuidancesCommand(
            campaign_id=str(campaign.id),
            chunk_recap_guidances="updated chunk",
        ),
    )

    assert current.chunk_recap_guidances == "chunk guidance"
    assert current.combined_recap_guidances == "combined guidance"
    assert updated.chunk_recap_guidances == "updated chunk"
    assert updated.combined_recap_guidances == "combined guidance"
    assert harness.recap_guidances.saved == [
        (campaign.id, "updated chunk", "combined guidance"),
    ]


def test_recap_guidance_use_cases_validate_campaign_and_updates() -> None:
    harness = Harness()
    campaign = harness.ready_campaign()
    get_guidances = GetRecapGuidances(harness.campaigns, harness.recap_guidances)
    update_guidances = UpdateRecapGuidances(
        harness.campaigns,
        harness.recap_guidances,
    )

    with pytest.raises(NotFoundError, match="was not found"):
        get_guidances.execute(GetRecapGuidancesCommand(campaign_id="missing"))
    with pytest.raises(InvalidOperationError, match="at least one"):
        update_guidances.execute(
            UpdateRecapGuidancesCommand(campaign_id=str(campaign.id)),
        )
    with pytest.raises(InvalidOperationError, match="must not be empty"):
        update_guidances.execute(
            UpdateRecapGuidancesCommand(
                campaign_id=str(campaign.id),
                combined_recap_guidances="  ",
            ),
        )


def test_add_voice_sample_imports_local_source_for_participant() -> None:
    harness = Harness()
    campaign = CreateCampaign(
        harness.campaigns,
        harness.ids,
        harness.recap_guidances,
    ).execute(
        CreateCampaignCommand(name="Storm King's Thunder"),
    ).campaign
    participant = AddParticipantToCampaign(
        harness.campaigns,
        harness.ids,
    ).execute(
        AddParticipantToCampaignCommand(
            campaign_id=campaign.id,
            display_name="Alice",
        ),
    ).participant
    source_path = Path("alice.wav").resolve()

    result = AddVoiceSample(
        harness.campaigns,
        harness.metadata_reader,
        harness.source_metadata_reader,
        harness.artifact_storage,
        harness.ids,
    ).execute(
        AddVoiceSampleCommand(
            campaign_id=str(campaign.id),
            participant_id=str(participant.id),
            source_path=str(source_path),
        ),
    )

    assert result.voice_sample.artifact.uri == (
        f"{campaign.id}/players/Alice/alice.wav"
    )
    assert result.voice_sample.metadata.checksum == "source-checksum:alice.wav"
    assert harness.source_metadata_reader.read_paths == [source_path]
    assert harness.artifact_storage.imports == [
        (campaign.id, "players", source_path, "Alice"),
    ]


def test_delete_campaign_can_preserve_or_remove_campaign_files() -> None:
    database_only_harness = Harness()
    database_only_campaign = database_only_harness.ready_campaign("Alice")

    DeleteCampaign(
        database_only_harness.campaigns,
        database_only_harness.artifact_storage,
    ).execute(
        DeleteCampaignCommand(campaign_id=str(database_only_campaign.id)),
    )

    assert database_only_harness.campaigns.get(database_only_campaign.id) is None
    assert database_only_harness.artifact_storage.deleted_campaigns == []

    full_delete_harness = Harness()
    full_delete_campaign = full_delete_harness.ready_campaign("Alice")

    DeleteCampaign(
        full_delete_harness.campaigns,
        full_delete_harness.artifact_storage,
    ).execute(
        DeleteCampaignCommand(
            campaign_id=str(full_delete_campaign.id),
            delete_files=True,
        ),
    )

    assert full_delete_harness.campaigns.get(full_delete_campaign.id) is None
    assert full_delete_harness.artifact_storage.deleted_campaigns == [
        full_delete_campaign.id,
    ]


def test_delete_campaign_keeps_database_record_when_file_deletion_fails() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    harness.artifact_storage.delete_error = InfrastructureError("disk unavailable")

    with pytest.raises(InfrastructureError, match="disk unavailable"):
        DeleteCampaign(harness.campaigns, harness.artifact_storage).execute(
            DeleteCampaignCommand(campaign_id=str(campaign.id), delete_files=True),
        )

    assert harness.campaigns.get(campaign.id) == campaign


def test_submit_recording_rejects_campaign_without_voice_samples() -> None:
    harness = Harness()
    harness.campaigns.save(Campaign(id=CampaignId("campaign-1"), name="Empty"))

    with pytest.raises(CampaignValidationError):
        harness.submit_use_case().execute(
            SubmitRecordingForProcessingCommand(
                campaign_id="campaign-1",
                artifact_uri="sessions/session-1.wav",
            ),
        )

    assert not harness.jobs.items
    assert not harness.audio_tracks.items


def test_submit_recording_normalizes_external_source_without_copying_or_deleting() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    source_path = Path("session.wav").resolve()

    result = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id=str(campaign.id),
            source_path=str(source_path),
            title="Session",
        ),
    )

    assert result.audio_track.artifact.uri == (
        f"{campaign.id}/records/normalized/audio-track-1.wav"
    )
    assert result.audio_track.metadata.codec == "pcm_s16le"
    assert result.normalized_count == 1
    assert result.bytes_freed == 75
    assert harness.artifact_storage.imports == []
    assert harness.artifact_storage.deleted_artifacts == []


def test_submit_recording_normalizes_and_deletes_managed_source() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    source = ArtifactRef(uri=f"{campaign.id}/records/session.wav")

    result = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id=str(campaign.id),
            artifact_uri=source.uri,
        ),
    )

    assert result.audio_track.artifact.uri.endswith(
        "/records/normalized/audio-track-1.wav",
    )
    assert harness.artifact_storage.deleted_artifacts == [source]


def test_source_cleanup_failure_does_not_roll_back_submitted_recording() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    harness.artifact_storage.artifact_delete_error = InfrastructureError(
        "file is locked",
    )

    result = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id=str(campaign.id),
            artifact_uri=f"{campaign.id}/records/session.wav",
        ),
    )

    assert result.job.status is JobStatus.PENDING
    assert harness.audio_tracks.get(result.audio_track.id) == result.audio_track
    assert result.cleanup_warnings
    assert "file is locked" in result.cleanup_warnings[0]


def test_register_and_replace_audio_track_use_canonical_artifact() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    register = RegisterAudioTrack(
        harness.campaigns,
        harness.metadata_reader,
        harness.ids,
        audio_normalizer=harness.audio_normalizer,
        artifact_storage=harness.artifact_storage,
    )
    registered = register.execute(
        RegisterAudioTrackCommand(
            campaign_id=str(campaign.id),
            artifact_uri=f"{campaign.id}/records/session.wav",
            title="Session",
        ),
    )
    update = UpdateAudioTrack(
        harness.campaigns,
        harness.metadata_reader,
        audio_normalizer=harness.audio_normalizer,
        artifact_storage=harness.artifact_storage,
    )

    renamed = update.execute(
        UpdateAudioTrackCommand(
            campaign_id=str(campaign.id),
            audio_track_id=str(registered.audio_track.id),
            artifact_uri=registered.audio_track.artifact.uri,
            title="Renamed",
        ),
    )
    replaced = update.execute(
        UpdateAudioTrackCommand(
            campaign_id=str(campaign.id),
            audio_track_id=str(registered.audio_track.id),
            artifact_uri=f"{campaign.id}/records/replacement.wav",
            title="Replacement",
        ),
    )

    assert renamed.normalized_count == 0
    assert len(harness.audio_normalizer.artifact_calls) == 2
    assert replaced.audio_track.artifact.uri == registered.audio_track.artifact.uri
    assert replaced.normalized_count == 1


@pytest.mark.parametrize(
    ("artifact_uri", "source_path"),
    [
        (None, None),
        ("sessions/session.wav", str(Path("session.wav").resolve())),
    ],
)
def test_submit_recording_requires_exactly_one_audio_source(
    artifact_uri: str | None,
    source_path: str | None,
) -> None:
    harness = Harness()
    harness.ready_campaign("Alice")

    with pytest.raises(
        InvalidOperationError,
        match="exactly one of artifact_uri or source_path",
    ):
        harness.submit_use_case().execute(
            SubmitRecordingForProcessingCommand(
                campaign_id="campaign-1",
                artifact_uri=artifact_uri,
                source_path=source_path,
            ),
        )

    assert harness.artifact_storage.imports == []


def test_create_processing_job_for_existing_audio_track() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    audio_track = AudioTrack(
        id="audio-track-1",
        campaign_id=campaign.id,
        artifact=ArtifactRef(
            uri="campaign-1/records/normalized/audio-track-1.wav",
        ),
        metadata=AudioMetadata(duration_seconds=12),
        title="Session 1",
    )
    campaign = add_audio_track(campaign, audio_track)
    harness.campaigns.save(campaign)
    harness.audio_tracks.save(audio_track)

    result = harness.create_job_for_audio_track_use_case().execute(
        CreateProcessingJobForAudioTrackCommand(audio_track_id="audio-track-1"),
    )

    assert result.campaign == campaign
    assert result.audio_track == audio_track
    assert result.job.id == ProcessingJobId("job-1")
    assert result.job.campaign_id == CampaignId("campaign-1")
    assert result.job.audio_track_id == audio_track.id
    assert result.job.status is JobStatus.PENDING
    assert harness.jobs.get(result.job.id) == result.job
    assert harness.audio_tracks.items == {audio_track.id: audio_track}
    assert harness.metadata_reader.read_artifacts == []


def test_create_processing_job_allows_multiple_jobs_for_same_audio_track() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    audio_track = AudioTrack(
        id="audio-track-1",
        campaign_id=campaign.id,
        artifact=ArtifactRef(
            uri="campaign-1/records/normalized/audio-track-1.wav",
        ),
        metadata=AudioMetadata(duration_seconds=12),
        title="Session 1",
    )
    campaign = add_audio_track(campaign, audio_track)
    harness.campaigns.save(campaign)
    harness.audio_tracks.save(audio_track)

    first = harness.create_job_for_audio_track_use_case().execute(
        CreateProcessingJobForAudioTrackCommand(audio_track_id="audio-track-1"),
    )
    second = harness.create_job_for_audio_track_use_case().execute(
        CreateProcessingJobForAudioTrackCommand(audio_track_id="audio-track-1"),
    )

    assert first.job.id == ProcessingJobId("job-1")
    assert second.job.id == ProcessingJobId("job-2")
    assert first.job.audio_track_id == second.job.audio_track_id == audio_track.id
    assert harness.jobs.list_for_audio_track(audio_track.id) == (
        first.job,
        second.job,
    )


def test_create_processing_job_rejects_unready_campaign() -> None:
    harness = Harness()
    participant = Participant(
        id=ParticipantId("participant-1"),
        campaign_id=CampaignId("campaign-1"),
        display_name="Alice",
    )
    audio_track = AudioTrack(
        id="audio-track-1",
        campaign_id=CampaignId("campaign-1"),
        artifact=ArtifactRef(
            uri="campaign-1/records/normalized/audio-track-1.wav",
        ),
        metadata=AudioMetadata(duration_seconds=12),
    )
    harness.campaigns.save(
        Campaign(
            id=CampaignId("campaign-1"),
            name="Unready",
            participants=(participant,),
            audio_tracks=(audio_track,),
        ),
    )
    harness.audio_tracks.save(audio_track)

    with pytest.raises(CampaignValidationError, match="has no voice sample"):
        harness.create_job_for_audio_track_use_case().execute(
            CreateProcessingJobForAudioTrackCommand(audio_track_id="audio-track-1"),
        )

    assert not harness.jobs.items
    assert harness.metadata_reader.read_artifacts == []


def test_restart_failed_processing_job_creates_new_pending_job() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    audio_track = AudioTrack(
        id="audio-track-1",
        campaign_id=campaign.id,
        artifact=ArtifactRef(
            uri="campaign-1/records/normalized/audio-track-1.wav",
        ),
        metadata=AudioMetadata(duration_seconds=12),
        title="Session 1",
    )
    campaign = add_audio_track(campaign, audio_track)
    harness.campaigns.save(campaign)
    harness.audio_tracks.save(audio_track)
    warning = PipelineWarning(
        kind=PipelineWarningKind.MISSING_VOICE_SAMPLE,
        message="sample missing",
    )
    failed = ProcessingJob(
        id=ProcessingJobId("job-failed"),
        campaign_id=campaign.id,
        audio_track_id=audio_track.id,
        status=JobStatus.FAILED,
        created_at=harness.clock.now(),
        updated_at=harness.clock.now(),
        transcript_id=TranscriptId("transcript-1"),
        warnings=(warning,),
        error_message="DeepSeek failed",
    )
    harness.jobs.save(failed)

    result = harness.restart_use_case().execute(
        RestartFailedProcessingJobCommand(job_id=failed.id),
    )

    assert result.source_job == failed
    assert result.audio_track == audio_track
    assert result.job.id == ProcessingJobId("job-1")
    assert result.job.status is JobStatus.PENDING
    assert result.job.audio_track_id == failed.audio_track_id
    assert result.job.transcript_id is None
    assert result.job.recap_id is None
    assert result.job.warnings == ()
    assert result.job.error_message is None
    assert result.job.updated_at == result.job.created_at
    assert harness.jobs.get(failed.id) == failed
    assert harness.jobs.get(result.job.id) == result.job


def test_restart_failed_processing_job_rejects_non_failed_job() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    audio_track = AudioTrack(
        id="audio-track-1",
        campaign_id=campaign.id,
        artifact=ArtifactRef(
            uri="campaign-1/records/normalized/audio-track-1.wav",
        ),
        metadata=AudioMetadata(duration_seconds=12),
        title="Session 1",
    )
    campaign = add_audio_track(campaign, audio_track)
    harness.campaigns.save(campaign)
    harness.audio_tracks.save(audio_track)
    pending = ProcessingJob(
        id=ProcessingJobId("job-pending"),
        campaign_id=campaign.id,
        audio_track_id=audio_track.id,
        status=JobStatus.PENDING,
        created_at=harness.clock.now(),
        updated_at=harness.clock.now(),
    )
    harness.jobs.save(pending)

    with pytest.raises(InvalidOperationError, match="must be failed"):
        harness.restart_use_case().execute(
            RestartFailedProcessingJobCommand(job_id=pending.id),
        )

    assert harness.jobs.items == {pending.id: pending}


def test_restart_canceled_processing_job_creates_new_pending_job() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    audio_track = AudioTrack(
        id="audio-track-1",
        campaign_id=campaign.id,
        artifact=ArtifactRef(
            uri="campaign-1/records/normalized/audio-track-1.wav",
        ),
        metadata=AudioMetadata(duration_seconds=12),
    )
    campaign = add_audio_track(campaign, audio_track)
    harness.campaigns.save(campaign)
    harness.audio_tracks.save(audio_track)
    canceled = ProcessingJob(
        id="job-canceled",
        campaign_id=campaign.id,
        audio_track_id=audio_track.id,
        status=JobStatus.CANCELED,
        created_at=harness.clock.now(),
        updated_at=harness.clock.now(),
    )
    harness.jobs.save(canceled)

    result = harness.restart_use_case().execute(
        RestartFailedProcessingJobCommand(job_id=canceled.id),
    )

    assert result.source_job == canceled
    assert result.job.status is JobStatus.PENDING
    assert harness.jobs.get(canceled.id) == canceled


def test_clear_failed_jobs_for_campaign_filters_and_deletes_only_failed_jobs() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    failed_jobs = tuple(
        ProcessingJob(
            id=ProcessingJobId(f"job-failed-{index}"),
            campaign_id=campaign.id,
            audio_track_id=AudioTrackId("audio-track-1"),
            status=JobStatus.FAILED,
            created_at=harness.clock.now(),
            updated_at=harness.clock.now(),
            error_message="failed",
        )
        for index in range(1, 3)
    )
    pending_job = ProcessingJob(
        id=ProcessingJobId("job-pending"),
        campaign_id=campaign.id,
        audio_track_id=AudioTrackId("audio-track-1"),
        status=JobStatus.PENDING,
        created_at=harness.clock.now(),
        updated_at=harness.clock.now(),
    )
    for job in (*failed_jobs, pending_job):
        harness.jobs.save(job)

    result = harness.clear_failed_jobs_use_case().execute(
        ClearFailedJobsForCampaignCommand(campaign_id=str(campaign.id)),
    )

    assert result.deleted_job_ids == ("job-failed-1", "job-failed-2")
    assert harness.failed_job_cleaner.calls == [(campaign.id, failed_jobs)]
    assert harness.jobs.items == {pending_job.id: pending_job}

    repeated = harness.clear_failed_jobs_use_case().execute(
        ClearFailedJobsForCampaignCommand(campaign_id=str(campaign.id)),
    )
    assert repeated.deleted_job_ids == ()
    assert len(harness.failed_job_cleaner.calls) == 1


def test_clear_failed_jobs_keeps_jobs_when_cleaner_fails() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    failed_job = ProcessingJob(
        id=ProcessingJobId("job-failed"),
        campaign_id=campaign.id,
        audio_track_id=AudioTrackId("audio-track-1"),
        status=JobStatus.FAILED,
        created_at=harness.clock.now(),
        updated_at=harness.clock.now(),
        error_message="failed",
    )
    harness.jobs.save(failed_job)
    harness.failed_job_cleaner.error = InfrastructureError("cleanup failed")

    with pytest.raises(InfrastructureError, match="cleanup failed"):
        harness.clear_failed_jobs_use_case().execute(
            ClearFailedJobsForCampaignCommand(campaign_id=str(campaign.id)),
        )

    assert harness.jobs.get(failed_job.id) == failed_job


def test_run_processing_job_completes_clean_mapping_flow() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    harness.transcriber.segments = (
        segment(0, 0, 1, "SPEAKER_00", "Hello there"),
    )
    harness.speaker_identifier.mappings = (
        confirmed_mapping("SPEAKER_00", "Alice", "participant-1"),
    )

    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
            title="Session 1",
        ),
    )
    result = harness.run_use_case(clean_transient=True).execute(
        RunProcessingJobCommand(job_id=submitted.job.id),
    )

    assert submitted.job.status is JobStatus.PENDING
    assert result.job.status is JobStatus.COMPLETED
    assert result.transcript is not None
    assert result.transcript.segments[0].speaker_label == SpeakerLabel.named("Alice")
    assert result.recap is not None
    assert result.recap.id in harness.recaps.items
    assert result.job.recap_id == result.recap.id
    assert harness.audio_processor.calls[0][1] == campaign.voice_samples
    assert harness.audio_processor.calls[0][2] == submitted.job.id
    assert harness.transcriber.audio == ArtifactRef(
        uri=f"prepared/{submitted.job.id}.wav",
    )
    assert harness.speaker_identifier.calls[0][2].audio_artifact == (
        harness.transcriber.audio
    )
    assert harness.speaker_mappings.records[0].job_id == submitted.job.id
    assert harness.speaker_mappings.records[0].mapping.source is (
        SpeakerMappingSource.AUTOMATIC
    )
    chunk_context = harness.recap_generator.generated_contexts[0]
    assert chunk_context.campaign_id == CampaignId("campaign-1")
    assert chunk_context.transcript_id == result.transcript.id
    assert chunk_context.recap_id == result.recap.id
    assert chunk_context.job_id == submitted.job.id
    assert chunk_context.chunk_index == 0
    assert harness.recap_generator.combined_contexts[0].chunk_index is None
    assert harness.transient_audio_cleaner.calls == [
        (CampaignId("campaign-1"), submitted.job.id),
    ]


def test_run_processing_job_always_cleans_transient_audio() -> None:
    harness = Harness()
    harness.ready_campaign("Alice")
    harness.audio_processor.error = InfrastructureError("ffmpeg failed")
    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )

    result = harness.run_use_case(clean_transient=True).execute(
        RunProcessingJobCommand(job_id=submitted.job.id),
    )

    assert result.job.status is JobStatus.FAILED
    assert harness.transient_audio_cleaner.calls == [
        (CampaignId("campaign-1"), submitted.job.id),
    ]


def test_run_processing_job_does_not_overwrite_concurrent_cancel() -> None:
    harness = Harness()
    harness.ready_campaign("Alice")
    harness.transcriber.segments = (
        segment(0, 0, 1, "SPEAKER_00", "Hello there"),
    )
    harness.speaker_identifier.mappings = (
        confirmed_mapping("SPEAKER_00", "Alice", "participant-1"),
    )
    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )
    original_save_if_status = harness.jobs.save_if_status

    def cancel_before_terminal_save(job, expected_status):
        if expected_status is JobStatus.RUNNING:
            current = harness.jobs.get(job.id)
            harness.jobs.save(replace(current, status=JobStatus.CANCELED))
            return False
        return original_save_if_status(job, expected_status)

    harness.jobs.save_if_status = cancel_before_terminal_save

    result = harness.run_use_case(clean_transient=True).execute(
        RunProcessingJobCommand(job_id=submitted.job.id),
    )

    assert result.job.status is JobStatus.CANCELED
    assert harness.jobs.get(submitted.job.id).status is JobStatus.CANCELED
    assert harness.transient_audio_cleaner.calls == [
        (CampaignId("campaign-1"), submitted.job.id),
    ]


def test_run_processing_job_waits_for_review_when_mapping_warnings_exist() -> None:
    harness = Harness()
    harness.ready_campaign("Alice", "Bob")
    harness.transcriber.segments = (
        segment(0, 0, 1, "SPEAKER_00", "Alice speaks"),
        segment(1, 1, 2, "SPEAKER_01", "Bob speaks"),
    )
    harness.speaker_identifier.mappings = (
        confirmed_mapping("SPEAKER_00", "Alice", "participant-1"),
    )

    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )
    result = harness.run_use_case(clean_transient=True).execute(
        RunProcessingJobCommand(job_id=submitted.job.id),
    )

    assert result.job.status is JobStatus.WAITING_FOR_REVIEW
    assert result.recap is None
    assert not harness.recaps.items
    assert not harness.recap_generator.generated_chunks
    assert PipelineWarningKind.UNRESOLVED_SPEAKER_LABEL in {
        warning.kind for warning in result.warnings
    }
    assert result.transcript is not None
    assert [segment.speaker_label.value for segment in result.transcript.segments] == [
        "Alice",
        "SPEAKER_01",
    ]
    assert harness.speaker_mappings.records[0].transcript_id == result.transcript.id
    assert harness.speaker_mappings.records[0].diagnostics[
        "prepared_audio_artifact_uri"
    ] == f"prepared/{submitted.job.id}.wav"
    assert harness.transient_audio_cleaner.calls == [
        (CampaignId("campaign-1"), submitted.job.id),
    ]


def test_run_processing_job_marks_failed_when_early_adapter_fails() -> None:
    harness = Harness()
    harness.ready_campaign("Alice")
    harness.audio_processor.error = PortExecutionError("ffmpeg failed")

    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )
    result = harness.run_use_case().execute(
        RunProcessingJobCommand(job_id=submitted.job.id),
    )

    assert result.job.status is JobStatus.FAILED
    assert result.job.error_message == "ffmpeg failed"
    assert result.job.updated_at > submitted.job.updated_at
    assert result.job.transcript_id is None
    assert result.transcript is None
    assert result.recap is None
    assert result.warnings == ()
    assert harness.transcripts.items == {}
    assert harness.recaps.items == {}
    assert harness.jobs.get(submitted.job.id) == result.job


def test_run_processing_job_failed_recap_preserves_persisted_transcript() -> None:
    harness = Harness()
    harness.ready_campaign("Alice")
    harness.transcriber.segments = (
        segment(0, 0, 1, "SPEAKER_00", "Hello there"),
    )
    harness.speaker_identifier.mappings = (
        confirmed_mapping("SPEAKER_00", "Alice", "participant-1"),
    )
    harness.recap_generator.generate_error = PortExecutionError("DeepSeek failed")

    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )
    result = harness.run_use_case().execute(
        RunProcessingJobCommand(job_id=submitted.job.id),
    )

    assert result.job.status is JobStatus.FAILED
    assert result.job.error_message == "DeepSeek failed"
    assert result.job.transcript_id == result.transcript.id
    assert result.job.recap_id is None
    assert result.transcript.id in harness.transcripts.items
    assert result.transcript.segments[0].speaker_label == SpeakerLabel.named("Alice")
    assert result.recap is None
    assert harness.recaps.items == {}
    assert harness.speaker_mappings.records[0].job_id == submitted.job.id
    assert harness.jobs.get(submitted.job.id) == result.job


def test_review_speaker_mappings_completes_job_after_manual_fix() -> None:
    harness = Harness()
    harness.ready_campaign("Alice", "Bob")
    harness.transcriber.segments = (
        segment(0, 0, 1, "SPEAKER_00", "Alice speaks"),
        segment(1, 1, 2, "SPEAKER_01", "Bob speaks"),
    )
    harness.speaker_identifier.mappings = (
        confirmed_mapping("SPEAKER_00", "Alice", "participant-1"),
    )
    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )
    waiting = harness.run_use_case().execute(
        RunProcessingJobCommand(job_id=submitted.job.id),
    )
    review_status_index = len(harness.jobs.saved_statuses)

    result = harness.review_use_case().execute(
        ReviewSpeakerMappingsCommand(
            job_id=waiting.job.id,
            mappings=(
                ManualSpeakerMappingCommand(
                    anonymous_label="SPEAKER_01",
                    participant_id="participant-2",
                    confidence=1.0,
                ),
            ),
        ),
    )

    assert result.job.status is JobStatus.COMPLETED
    assert not result.warnings
    assert result.recap is not None
    assert result.job.recap_id == result.recap.id
    assert [segment.speaker_label.value for segment in result.transcript.segments] == [
        "Alice",
        "Bob",
    ]
    assert result.applied_mappings[0].source is SpeakerMappingSource.MANUAL
    assert len(harness.speaker_mappings.records) == 2
    assert harness.speaker_mappings.records[-1].mapping.source is (
        SpeakerMappingSource.MANUAL
    )
    assert harness.speaker_mappings.records[-1].diagnostics == {"warning_count": 0}
    assert harness.jobs.saved_statuses[review_status_index:] == [
        JobStatus.RUNNING,
        JobStatus.COMPLETED,
    ]


def test_review_speaker_mappings_completes_with_custom_and_kept_labels() -> None:
    harness = Harness()
    harness.ready_campaign("Alice")
    harness.transcriber.segments = (
        segment(0, 0, 1, "SPEAKER_00", "Alice speaks"),
        segment(1, 1, 2, "SPEAKER_01", "A guest speaks"),
        segment(2, 2, 3, "SPEAKER_02", "Another guest speaks"),
    )
    harness.speaker_identifier.mappings = (
        confirmed_mapping("SPEAKER_00", "Alice", "participant-1"),
    )
    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )
    waiting = harness.run_use_case().execute(
        RunProcessingJobCommand(job_id=submitted.job.id),
    )
    review_status_index = len(harness.jobs.saved_statuses)

    result = harness.review_use_case().execute(
        ReviewSpeakerMappingsCommand(
            job_id=waiting.job.id,
            mappings=(
                ManualSpeakerMappingCommand(
                    anonymous_label="SPEAKER_01",
                    named_label=" Random Guest ",
                    confidence=1.0,
                ),
                ManualSpeakerMappingCommand(
                    anonymous_label="SPEAKER_02",
                    named_label="SPEAKER_02",
                    confidence=1.0,
                ),
            ),
        ),
    )

    assert result.job.status is JobStatus.COMPLETED
    assert result.warnings == ()
    assert result.recap is not None
    assert [segment.speaker_label for segment in result.transcript.segments] == [
        SpeakerLabel.named("Alice"),
        SpeakerLabel.named("Random Guest"),
        SpeakerLabel.named("SPEAKER_02"),
    ]
    manual_records = harness.speaker_mappings.records[-2:]
    assert all(record.mapping.participant_id is None for record in manual_records)
    assert harness.jobs.saved_statuses[review_status_index:] == [
        JobStatus.RUNNING,
        JobStatus.COMPLETED,
    ]


def test_review_speaker_mappings_partial_review_stays_waiting() -> None:
    harness = Harness()
    harness.ready_campaign("Alice")
    harness.transcriber.segments = (
        segment(0, 0, 1, "SPEAKER_00", "A guest speaks"),
        segment(1, 1, 2, "SPEAKER_01", "Another guest speaks"),
    )
    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )
    waiting = harness.run_use_case().execute(
        RunProcessingJobCommand(job_id=submitted.job.id),
    )
    review_status_index = len(harness.jobs.saved_statuses)

    result = harness.review_use_case().execute(
        ReviewSpeakerMappingsCommand(
            job_id=waiting.job.id,
            mappings=(
                ManualSpeakerMappingCommand(
                    anonymous_label="SPEAKER_00",
                    named_label="Random Guest",
                    confidence=1.0,
                ),
            ),
        ),
    )

    assert result.job.status is JobStatus.WAITING_FOR_REVIEW
    assert result.recap is None
    assert [segment.speaker_label.value for segment in result.transcript.segments] == [
        "Random Guest",
        "SPEAKER_01",
    ]
    assert PipelineWarningKind.UNRESOLVED_SPEAKER_LABEL in {
        warning.kind for warning in result.warnings
    }
    assert harness.jobs.saved_statuses[review_status_index:] == [
        JobStatus.RUNNING,
        JobStatus.WAITING_FOR_REVIEW,
    ]


def test_review_speaker_mappings_marks_running_job_failed_on_error() -> None:
    harness, waiting_job = _waiting_review_job()
    harness.recap_generator.generate_error = PortExecutionError("DeepSeek failed")
    review_status_index = len(harness.jobs.saved_statuses)

    with pytest.raises(PortExecutionError, match="DeepSeek failed"):
        harness.review_use_case().execute(_review_bob_command(waiting_job))

    saved = harness.jobs.get(waiting_job.id)
    assert saved.status is JobStatus.FAILED
    assert saved.error_message == "DeepSeek failed"
    assert harness.jobs.saved_statuses[review_status_index:] == [
        JobStatus.RUNNING,
        JobStatus.FAILED,
    ]


def test_review_speaker_mappings_rejects_concurrent_claim() -> None:
    harness, waiting_job = _waiting_review_job()
    original_save_if_status = harness.jobs.save_if_status

    def lose_claim(job, expected_status):
        if expected_status is JobStatus.WAITING_FOR_REVIEW:
            current = harness.jobs.get(job.id)
            harness.jobs.save(replace(current, status=JobStatus.RUNNING))
            return False
        return original_save_if_status(job, expected_status)

    harness.jobs.save_if_status = lose_claim

    with pytest.raises(
        InvalidOperationError,
        match="no longer waiting for review",
    ):
        harness.review_use_case().execute(_review_bob_command(waiting_job))

    assert harness.jobs.get(waiting_job.id).status is JobStatus.RUNNING


def test_review_speaker_mappings_does_not_overwrite_concurrent_cancel() -> None:
    harness, waiting_job = _waiting_review_job()
    original_save_if_status = harness.jobs.save_if_status
    review_status_index = len(harness.jobs.saved_statuses)

    def cancel_before_terminal_save(job, expected_status):
        if (
            expected_status is JobStatus.RUNNING
            and job.status is JobStatus.COMPLETED
        ):
            current = harness.jobs.get(job.id)
            harness.jobs.save(replace(current, status=JobStatus.CANCELED))
            return False
        return original_save_if_status(job, expected_status)

    harness.jobs.save_if_status = cancel_before_terminal_save

    result = harness.review_use_case().execute(_review_bob_command(waiting_job))

    assert result.job.status is JobStatus.CANCELED
    assert harness.jobs.get(waiting_job.id).status is JobStatus.CANCELED
    assert harness.jobs.saved_statuses[review_status_index:] == [
        JobStatus.RUNNING,
        JobStatus.CANCELED,
    ]


def _waiting_review_job() -> tuple[Harness, ProcessingJob]:
    harness = Harness()
    harness.ready_campaign("Alice", "Bob")
    harness.transcriber.segments = (
        segment(0, 0, 1, "SPEAKER_00", "Alice speaks"),
        segment(1, 1, 2, "SPEAKER_01", "Bob speaks"),
    )
    harness.speaker_identifier.mappings = (
        confirmed_mapping("SPEAKER_00", "Alice", "participant-1"),
    )
    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )
    waiting = harness.run_use_case().execute(
        RunProcessingJobCommand(job_id=submitted.job.id),
    )
    return harness, waiting.job


def _review_bob_command(job: ProcessingJob) -> ReviewSpeakerMappingsCommand:
    return ReviewSpeakerMappingsCommand(
        job_id=job.id,
        mappings=(
            ManualSpeakerMappingCommand(
                anonymous_label="SPEAKER_01",
                participant_id="participant-2",
                confidence=1.0,
            ),
        ),
    )


@pytest.mark.parametrize(
    "mappings",
    (
        (
            ManualSpeakerMappingCommand(
                anonymous_label="SPEAKER_00",
                named_label=" ",
            ),
        ),
        (
            ManualSpeakerMappingCommand(
                anonymous_label="SPEAKER_00",
                participant_id="participant-1",
                named_label="Guest",
            ),
        ),
        (
            ManualSpeakerMappingCommand(
                anonymous_label="SPEAKER_00",
                participant_id="participant-1",
            ),
            ManualSpeakerMappingCommand(
                anonymous_label="SPEAKER_00",
                named_label="Guest",
            ),
        ),
    ),
)
def test_review_speaker_mappings_rejects_invalid_manual_decisions(
    mappings: tuple[ManualSpeakerMappingCommand, ...],
) -> None:
    harness = Harness()
    harness.ready_campaign("Alice")
    harness.transcriber.segments = (
        segment(0, 0, 1, "SPEAKER_00", "A guest speaks"),
    )
    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )
    waiting = harness.run_use_case().execute(
        RunProcessingJobCommand(job_id=submitted.job.id),
    )

    with pytest.raises(InvalidOperationError):
        harness.review_use_case().execute(
            ReviewSpeakerMappingsCommand(
                job_id=waiting.job.id,
                mappings=mappings,
            ),
        )


def test_generate_recap_and_export_markdown_use_artifact_storage() -> None:
    harness = Harness()
    transcript = Transcript(
        id=TranscriptId("transcript-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id="audio-track-1",
        segments=(
            TranscriptSegment(
                index=0,
                time_range=TimeRange(0, 5),
                speaker_label=SpeakerLabel.named("Alice"),
                text="We enter the crypt.",
            ),
        ),
    )
    harness.transcripts.save(transcript)
    old_recap = Recap(
        id="recap-old",
        transcript_id=transcript.id,
        markdown="# Old recap",
    )
    harness.recaps.save(old_recap)
    job = ProcessingJob(
        id="job-1",
        campaign_id=transcript.campaign_id,
        audio_track_id=transcript.audio_track_id,
        status=JobStatus.COMPLETED,
        created_at=datetime(2026, 1, 1, 10, 0, 0),
        updated_at=datetime(2026, 1, 1, 11, 0, 0),
        transcript_id=transcript.id,
        recap_id=old_recap.id,
    )
    harness.jobs.save(job)

    recap_result = GenerateRecap(
        harness.jobs,
        harness.transcripts,
        harness.recaps,
        harness.tokenizer,
        harness.recap_guidances,
        harness.recap_generator,
        harness.clock,
        harness.ids,
    ).execute(GenerateRecapCommand(job_id=job.id))
    transcript_export = ExportTranscriptMarkdown(
        harness.transcripts,
        harness.artifact_storage,
    ).execute(ExportTranscriptMarkdownCommand(transcript_id=transcript.id))
    recap_export = ExportRecapMarkdown(
        harness.recaps,
        harness.artifact_storage,
    ).execute(ExportRecapMarkdownCommand(recap_id=recap_result.recap.id))

    assert transcript_export.artifact.uri == "memory://transcript-transcript-1.md"
    assert recap_export.artifact.uri == "memory://recap-recap-1.md"
    assert recap_result.job.recap_id == recap_result.recap.id
    assert recap_result.job.transcript_id == transcript.id
    assert recap_result.job.status is JobStatus.COMPLETED
    assert recap_result.job.updated_at == datetime(2026, 1, 1, 12, 0, 0)
    assert harness.jobs.get(job.id) == recap_result.job
    assert harness.recaps.get(old_recap.id) == old_recap
    assert harness.transcripts.get(transcript.id) == transcript
    assert (
        harness.recap_generator.generated_contexts[0].recap_id
        == recap_result.recap.id
    )
    assert harness.recap_generator.generated_contexts[0].job_id == job.id
    assert harness.recap_generator.generated_guidances == ["chunk guidance"]
    assert harness.recap_generator.combined_guidances == ["combined guidance"]
    assert harness.recap_guidances.chunk_reads == [transcript.campaign_id]
    assert harness.recap_guidances.combined_reads == [transcript.campaign_id]
    transcript_content = harness.artifact_storage.saved["transcript-transcript-1.md"][0]
    recap_content = harness.artifact_storage.saved["recap-recap-1.md"][0]
    assert "[00:00:00 - 00:00:05] **Alice:** We enter the crypt." in transcript_content
    assert "## Summary" in recap_content


def test_generate_recap_rejects_job_without_transcript() -> None:
    harness = Harness()
    job = ProcessingJob(
        id="job-1",
        campaign_id="campaign-1",
        audio_track_id="audio-track-1",
        status=JobStatus.PENDING,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    harness.jobs.save(job)

    with pytest.raises(InvalidOperationError, match="has no transcript"):
        GenerateRecap(
            harness.jobs,
            harness.transcripts,
            harness.recaps,
            harness.tokenizer,
            harness.recap_guidances,
            harness.recap_generator,
            harness.clock,
            harness.ids,
        ).execute(GenerateRecapCommand(job_id=job.id))

    assert harness.jobs.get(job.id) == job
    assert harness.recaps.items == {}


def test_generate_recap_failure_preserves_existing_job_recap() -> None:
    harness = Harness()
    transcript = Transcript(
        id="transcript-1",
        campaign_id="campaign-1",
        audio_track_id="audio-track-1",
        segments=(
            TranscriptSegment(
                index=0,
                time_range=TimeRange(0, 5),
                speaker_label=SpeakerLabel.named("Alice"),
                text="We enter the crypt.",
            ),
        ),
    )
    job = ProcessingJob(
        id="job-1",
        campaign_id="campaign-1",
        audio_track_id="audio-track-1",
        status=JobStatus.COMPLETED,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        transcript_id=transcript.id,
        recap_id="recap-old",
    )
    harness.transcripts.save(transcript)
    harness.jobs.save(job)
    harness.recap_generator.generate_error = PortExecutionError("DeepSeek failed")

    with pytest.raises(PortExecutionError, match="DeepSeek failed"):
        GenerateRecap(
            harness.jobs,
            harness.transcripts,
            harness.recaps,
            harness.tokenizer,
            harness.recap_guidances,
            harness.recap_generator,
            harness.clock,
            harness.ids,
        ).execute(GenerateRecapCommand(job_id=job.id))

    assert harness.jobs.get(job.id) == job
    assert harness.recaps.items == {}
    assert harness.transcripts.get(transcript.id) == transcript


def test_get_job_status_returns_saved_job() -> None:
    harness = Harness()
    harness.ready_campaign("Alice")
    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )

    result = GetJobStatus(harness.jobs).execute(
        GetJobStatusCommand(job_id=submitted.job.id),
    )

    assert result.job == submitted.job


def test_query_use_cases_list_jobs_inspect_metadata_and_preview_markdown() -> None:
    harness = Harness()
    harness.ready_campaign("Alice")
    submitted = harness.submit_use_case().execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri="sessions/session-1.wav",
        ),
    )
    transcript = Transcript(
        id=TranscriptId("transcript-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=submitted.audio_track.id,
        segments=(
            TranscriptSegment(
                index=0,
                time_range=TimeRange(0, 5),
                speaker_label=SpeakerLabel.named("Alice"),
                text="We enter the crypt.",
            ),
            TranscriptSegment(
                index=1,
                time_range=TimeRange(5, 9),
                speaker_label=SpeakerLabel.named("Bob"),
                text="I light a torch.",
            ),
        ),
    )
    recap = Recap(
        id="recap-1",
        transcript_id=transcript.id,
        markdown="# Recap\n\nDone.",
    )
    harness.transcripts.save(transcript)
    harness.recaps.save(recap)

    jobs = ListJobsForCampaign(
        harness.campaigns,
        harness.jobs,
    ).execute(
        ListJobsForCampaignCommand(campaign_id="campaign-1"),
    )
    metadata = InspectAudioMetadata(harness.metadata_reader).execute(
        InspectAudioMetadataCommand(artifact_uri="sessions/session-2.wav"),
    )
    local_metadata = InspectLocalAudioFile(
        harness.source_metadata_reader,
    ).execute(
        InspectLocalAudioFileCommand(source_path="session.wav"),
    )
    transcript_preview = PreviewTranscriptMarkdown(harness.transcripts).execute(
        PreviewTranscriptMarkdownCommand(transcript_id=transcript.id),
    )
    recap_preview = PreviewRecapMarkdown(harness.recaps).execute(
        PreviewRecapMarkdownCommand(recap_id=recap.id),
    )

    assert jobs.jobs == (submitted.job,)
    assert metadata.metadata.checksum == "checksum:sessions/session-2.wav"
    assert local_metadata.source_path == str(Path("session.wav").resolve())
    assert local_metadata.metadata.checksum == "source-checksum:session.wav"
    assert (
        "[00:00:00 - 00:00:05] **Alice:** We enter the crypt.\n\n"
        "[00:00:05 - 00:00:09] **Bob:** I light a torch."
        in transcript_preview.markdown
    )
    assert recap_preview.markdown == "# Recap\n\nDone."


def test_sync_campaign_folder_adds_players_samples_and_records() -> None:
    harness = Harness()
    harness.campaigns.save(Campaign(id=CampaignId("campaign-1"), name="Synced"))
    harness.folder_scanner.snapshot = CampaignFolderSnapshot(
        campaign_id="campaign-1",
        voice_samples=(
            ScannedVoiceSampleArtifact(
                player_name="Alice",
                artifact=ArtifactRef(uri="campaign-1/players/Alice/sample.wav"),
            ),
        ),
        audio_tracks=(
            ScannedAudioTrackArtifact(
                artifact=ArtifactRef(uri="campaign-1/records/session-1.wav"),
                title="session-1",
            ),
        ),
    )

    result = harness.sync_use_case().execute(
        SyncCampaignFolderCommand(campaign_id="campaign-1"),
    )

    assert result.participants_created == 1
    assert result.voice_samples_added == 1
    assert result.audio_tracks_added == 1
    assert result.campaign.participants[0].display_name == "Alice"
    assert result.campaign.voice_samples[0].participant_id == ParticipantId(
        "participant-1",
    )
    assert result.campaign.audio_tracks[0].title == "session-1"


def test_sync_normalizes_new_record_and_preserves_canonical_on_next_scan() -> None:
    harness = Harness()
    harness.campaigns.save(Campaign(id=CampaignId("campaign-1"), name="Synced"))
    source = ArtifactRef(uri="campaign-1/records/session-1.wav")
    harness.folder_scanner.snapshot = CampaignFolderSnapshot(
        campaign_id="campaign-1",
        audio_tracks=(ScannedAudioTrackArtifact(artifact=source, title="session-1"),),
    )

    first = harness.sync_use_case().execute(
        SyncCampaignFolderCommand(campaign_id="campaign-1"),
    )
    harness.folder_scanner.snapshot = CampaignFolderSnapshot(campaign_id="campaign-1")
    second = harness.sync_use_case().execute(
        SyncCampaignFolderCommand(campaign_id="campaign-1"),
    )

    assert first.audio_tracks_normalized == 1
    assert first.bytes_freed == 75
    assert first.campaign.audio_tracks[0].artifact.uri == (
        "campaign-1/records/normalized/audio-track-1.wav"
    )
    assert harness.artifact_storage.deleted_artifacts == [source]
    assert second.audio_tracks_deleted == 0
    assert second.campaign.audio_tracks == first.campaign.audio_tracks


def test_sync_recovers_committed_normalization_without_duplicate_track() -> None:
    harness = Harness()
    harness.campaigns.save(Campaign(id=CampaignId("campaign-1"), name="Synced"))
    source = ArtifactRef(uri="campaign-1/records/session-1.wav")
    source_metadata = harness.metadata_reader.read(source)
    harness.audio_normalizer.recovered = harness.audio_normalizer._result(
        CampaignId("campaign-1"),
        AudioTrackId("audio-track-recovered"),
        source_metadata,
    )
    harness.folder_scanner.snapshot = CampaignFolderSnapshot(
        campaign_id="campaign-1",
        audio_tracks=(ScannedAudioTrackArtifact(artifact=source, title="session-1"),),
    )

    result = harness.sync_use_case().execute(
        SyncCampaignFolderCommand(campaign_id="campaign-1"),
    )

    assert len(result.campaign.audio_tracks) == 1
    assert result.campaign.audio_tracks[0].id == AudioTrackId(
        "audio-track-recovered",
    )
    assert result.audio_tracks_normalized == 0
    assert harness.artifact_storage.deleted_artifacts == [source]


def test_sync_campaign_folder_removes_missing_files_and_only_pending_jobs() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    audio_track = AudioTrack(
        id="audio-track-old",
        campaign_id=campaign.id,
        artifact=ArtifactRef(
            uri="campaign-1/records/normalized/audio-track-old.wav",
        ),
        metadata=AudioMetadata(duration_seconds=12),
        title="old",
    )
    campaign = add_audio_track(campaign, audio_track)
    harness.campaigns.save(campaign)
    pending = ProcessingJob(
        id=ProcessingJobId("job-pending"),
        campaign_id=campaign.id,
        audio_track_id=audio_track.id,
        status=JobStatus.PENDING,
        created_at=harness.clock.now(),
        updated_at=harness.clock.now(),
    )
    completed = ProcessingJob(
        id=ProcessingJobId("job-completed"),
        campaign_id=campaign.id,
        audio_track_id=audio_track.id,
        status=JobStatus.COMPLETED,
        created_at=harness.clock.now(),
        updated_at=harness.clock.now(),
    )
    harness.jobs.save(pending)
    harness.jobs.save(completed)
    harness.artifact_storage.missing_artifact_uris.add(
        audio_track.artifact.uri,
    )
    harness.folder_scanner.snapshot = CampaignFolderSnapshot(campaign_id="campaign-1")

    result = harness.sync_use_case().execute(
        SyncCampaignFolderCommand(campaign_id="campaign-1"),
    )

    assert result.voice_samples_deleted == 1
    assert result.audio_tracks_deleted == 1
    assert result.pending_jobs_deleted == 1
    assert result.campaign.participants[0].display_name == "Alice"
    assert result.campaign.voice_samples == ()
    assert result.campaign.audio_tracks == ()
    assert harness.jobs.get(pending.id) is None
    assert harness.jobs.get(completed.id) == completed


def segment(
    index: int,
    start: float,
    end: float,
    speaker_label: str,
    text: str,
) -> TranscriptSegment:
    return TranscriptSegment(
        index=index,
        time_range=TimeRange(start, end),
        speaker_label=SpeakerLabel.anonymous(speaker_label),
        text=text,
    )


def confirmed_mapping(
    anonymous: str,
    named: str,
    participant_id: str,
) -> SpeakerMapping:
    return SpeakerMapping(
        anonymous_label=SpeakerLabel.anonymous(anonymous),
        named_label=SpeakerLabel.named(named),
        participant_id=ParticipantId(participant_id),
        confidence=0.95,
        source=SpeakerMappingSource.AUTOMATIC,
        status=SpeakerMappingStatus.CONFIRMED,
    )
