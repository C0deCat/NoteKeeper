from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from notekeeper.application import (
    AddParticipantToCampaign,
    AddParticipantToCampaignCommand,
    AddVoiceSample,
    AddVoiceSampleCommand,
    CampaignFolderSnapshot,
    CreateCampaign,
    CreateCampaignCommand,
    ExportRecapMarkdown,
    ExportRecapMarkdownCommand,
    ExportTranscriptMarkdown,
    ExportTranscriptMarkdownCommand,
    GenerateRecap,
    GenerateRecapCommand,
    GetJobStatus,
    GetJobStatusCommand,
    ManualSpeakerMappingCommand,
    ReviewSpeakerMappings,
    ReviewSpeakerMappingsCommand,
    RunProcessingJob,
    RunProcessingJobCommand,
    ScannedAudioTrackArtifact,
    ScannedVoiceSampleArtifact,
    SubmitRecordingForProcessing,
    SubmitRecordingForProcessingCommand,
    SyncCampaignFolder,
    SyncCampaignFolderCommand,
    TranscriptChunk,
)
from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrack,
    Campaign,
    CampaignId,
    CampaignValidationError,
    JobStatus,
    Participant,
    ParticipantId,
    PipelineWarningKind,
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


class InMemoryRepository:
    def __init__(self) -> None:
        self.items = {}

    def get(self, item_id):
        return self.items.get(item_id)

    def list(self):
        return tuple(self.items.values())

    def save(self, item) -> None:
        self.items[item.id] = item

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


class FakeAudioProcessor:
    def __init__(self) -> None:
        self.calls: list[tuple[AudioTrack, tuple[VoiceSample, ...]]] = []

    def prepare_session_audio(
        self,
        audio_track: AudioTrack,
        voice_samples: tuple[VoiceSample, ...],
    ) -> ArtifactRef:
        self.calls.append((audio_track, voice_samples))
        return ArtifactRef(uri=f"prepared:{audio_track.artifact.uri}")


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
        self.calls: list[tuple[Campaign, Transcript]] = []

    def identify(
        self,
        campaign: Campaign,
        transcript: Transcript,
    ) -> tuple[SpeakerMapping, ...]:
        self.calls.append((campaign, transcript))
        return self.mappings


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


class FakeRecapGenerator:
    def __init__(self) -> None:
        self.generated_chunks: list[TranscriptChunk] = []
        self.combined_chunks: tuple[RecapChunk, ...] = ()

    def generate_chunk(self, chunk: TranscriptChunk) -> str:
        self.generated_chunks.append(chunk)
        return f"Chunk recap: {chunk.text or 'empty transcript'}"

    def combine_chunks(self, chunks: tuple[RecapChunk, ...]) -> str:
        self.combined_chunks = chunks
        chunk_text = "\n\n".join(chunk.markdown for chunk in chunks)
        return f"{chunk_text}\n\n## Summary\nDone"


class FakeArtifactStorage:
    def __init__(self) -> None:
        self.saved: dict[str, tuple[str, str, ArtifactRef]] = {}

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
        self.metadata_reader = FakeMetadataReader()
        self.audio_processor = FakeAudioProcessor()
        self.transcriber = FakeTranscriber()
        self.speaker_identifier = FakeSpeakerIdentifier()
        self.tokenizer = FakeTokenizer()
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
            self.clock,
            self.ids,
        )

    def run_use_case(self) -> RunProcessingJob:
        return RunProcessingJob(
            self.campaigns,
            self.audio_tracks,
            self.transcripts,
            self.recaps,
            self.jobs,
            self.audio_processor,
            self.transcriber,
            self.speaker_identifier,
            self.tokenizer,
            self.recap_generator,
            self.clock,
            self.ids,
        )

    def review_use_case(self) -> ReviewSpeakerMappings:
        return ReviewSpeakerMappings(
            self.campaigns,
            self.transcripts,
            self.recaps,
            self.jobs,
            self.tokenizer,
            self.recap_generator,
            self.clock,
            self.ids,
        )

    def sync_use_case(self) -> SyncCampaignFolder:
        return SyncCampaignFolder(
            self.campaigns,
            self.jobs,
            self.folder_scanner,
            self.metadata_reader,
            self.ids,
        )


def test_campaign_use_cases_create_campaign_add_participant_and_voice_sample() -> None:
    harness = Harness()

    campaign = CreateCampaign(harness.campaigns, harness.ids).execute(
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
        harness.ids,
    ).execute(
        AddVoiceSampleCommand(
            campaign_id=campaign.id,
            participant_id=participant_result.participant.id,
            artifact_uri="samples/alice.wav",
        ),
    )

    assert campaign.id == CampaignId("campaign-1")
    assert participant_result.participant.id == ParticipantId("participant-1")
    assert sample_result.voice_sample.id == VoiceSampleId("voice-sample-1")
    assert sample_result.voice_sample.metadata.checksum == "checksum:samples/alice.wav"
    assert harness.campaigns.get(campaign.id).voice_samples == (
        sample_result.voice_sample,
    )


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
    result = harness.run_use_case().execute(
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
    result = harness.run_use_case().execute(
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

    recap_result = GenerateRecap(
        harness.transcripts,
        harness.recaps,
        harness.tokenizer,
        harness.recap_generator,
        harness.ids,
    ).execute(GenerateRecapCommand(transcript_id=transcript.id))
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
    transcript_content = harness.artifact_storage.saved["transcript-transcript-1.md"][0]
    recap_content = harness.artifact_storage.saved["recap-recap-1.md"][0]
    assert "[00:00:00 - 00:00:05] **Alice:** We enter the crypt." in transcript_content
    assert "## Summary" in recap_content


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


def test_sync_campaign_folder_removes_missing_files_and_only_pending_jobs() -> None:
    harness = Harness()
    campaign = harness.ready_campaign("Alice")
    audio_track = AudioTrack(
        id="audio-track-old",
        campaign_id=campaign.id,
        artifact=ArtifactRef(uri="campaign-1/records/old.wav"),
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
