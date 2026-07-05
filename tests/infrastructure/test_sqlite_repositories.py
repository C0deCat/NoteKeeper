from __future__ import annotations

from datetime import datetime
from pathlib import Path

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
    Recap,
    RecapChunk,
    RecapId,
    SpeakerLabel,
    SpeakerMapping,
    SpeakerMappingSource,
    SpeakerMappingStatus,
    TimeRange,
    Transcript,
    TranscriptId,
    TranscriptSegment,
    VoiceSample,
    VoiceSampleId,
)
from notekeeper.application import SpeakerMappingRecord
from notekeeper.infrastructure.filesystem import LocalCampaignArtifactStorage
from notekeeper.infrastructure.sqlite import (
    SQLiteAudioTrackRepository,
    SQLiteCampaignRepository,
    SQLiteDatabase,
    SQLiteJobRepository,
    SQLiteRecapRepository,
    SQLiteSpeakerMappingRepository,
    SQLiteTranscriptRepository,
    SQLiteVoiceSampleRepository,
)


def test_sqlite_campaign_repository_reconstructs_aggregate(tmp_path: Path) -> None:
    database = _database(tmp_path)
    campaign_repository = SQLiteCampaignRepository(database)
    voice_samples = SQLiteVoiceSampleRepository(database)
    audio_tracks = SQLiteAudioTrackRepository(database)
    campaign = _campaign()

    campaign_repository.save(campaign)
    loaded = campaign_repository.get(campaign.id)

    assert loaded == campaign
    assert campaign_repository.list() == (campaign,)
    assert voice_samples.get_by_artifact_uri(
        campaign.id,
        "campaign-1/players/Alice/sample.wav",
    ) == campaign.voice_samples[0]
    assert audio_tracks.get_by_artifact_uri(
        campaign.id,
        "campaign-1/records/session.wav",
    ) == campaign.audio_tracks[0]

    campaign_repository.delete(campaign.id)

    assert campaign_repository.get(campaign.id) is None
    assert voice_samples.list_for_campaign(campaign.id) == ()
    assert audio_tracks.list_for_campaign(campaign.id) == ()


def test_sqlite_transcript_and_recap_repositories_store_payload_files(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    campaign_repository = SQLiteCampaignRepository(database)
    transcript_repository = SQLiteTranscriptRepository(database, storage)
    recap_repository = SQLiteRecapRepository(database, storage)
    campaign = _campaign()
    campaign_repository.save(campaign)
    transcript = Transcript(
        id=TranscriptId("transcript-1"),
        campaign_id=campaign.id,
        audio_track_id=campaign.audio_tracks[0].id,
        segments=(
            TranscriptSegment(
                index=0,
                time_range=TimeRange(0, 5),
                speaker_label=SpeakerLabel.named("Alice"),
                text="Hello",
            ),
        ),
    )
    recap = Recap(
        id=RecapId("recap-1"),
        transcript_id=transcript.id,
        markdown="## Summary\nDone",
        chunks=(
            RecapChunk(
                markdown="Done",
                time_range=TimeRange(0, 5),
                source_segment_indexes=(0,),
            ),
        ),
    )

    transcript_repository.save(transcript)
    recap_repository.save(recap)

    assert transcript_repository.get(transcript.id) == transcript
    assert transcript_repository.list_for_audio_track(transcript.audio_track_id) == (
        transcript,
    )
    assert recap_repository.get(recap.id) == recap
    assert recap_repository.list_for_transcript(transcript.id) == (recap,)
    assert transcript_repository.payload_uri(transcript.id) == (
        "campaign-1/transcripts/transcript-1.json"
    )
    assert recap_repository.payload_uri(recap.id) == "campaign-1/recaps/recap-1.json"
    assert (
        tmp_path / "artifacts" / "campaign-1" / "transcripts" / "transcript-1.json"
    ).is_file()


def test_sqlite_job_repository_lists_and_deletes_by_audio_track(tmp_path: Path) -> None:
    database = _database(tmp_path)
    jobs = SQLiteJobRepository(database)
    job = ProcessingJob(
        id=ProcessingJobId("job-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
        status=JobStatus.PENDING,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 1),
    )

    jobs.save(job)

    assert jobs.get(job.id) == job
    assert jobs.list_for_campaign(job.campaign_id) == (job,)
    assert jobs.list_for_audio_track(job.audio_track_id) == (job,)

    jobs.delete(job.id)

    assert jobs.get(job.id) is None


def test_sqlite_job_repository_round_trips_failed_job_error(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    jobs = SQLiteJobRepository(database)
    job = ProcessingJob(
        id=ProcessingJobId("job-failed"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
        status=JobStatus.FAILED,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 5),
        transcript_id=TranscriptId("transcript-1"),
        error_message="DeepSeek failed",
    )

    jobs.save(job)

    assert jobs.get(job.id) == job
    assert jobs.get(job.id).error_message == "DeepSeek failed"


def test_sqlite_speaker_mapping_repository_round_trips_records(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    mappings = SQLiteSpeakerMappingRepository(database)
    record = SpeakerMappingRecord(
        job_id=ProcessingJobId("job-1"),
        transcript_id=TranscriptId("transcript-1"),
        mapping=SpeakerMapping(
            anonymous_label=SpeakerLabel.anonymous("SPEAKER_00"),
            named_label=SpeakerLabel.named("Alice"),
            participant_id=ParticipantId("participant-1"),
            confidence=0.875,
            source=SpeakerMappingSource.SAMPLE_BASED,
            status=SpeakerMappingStatus.CONFIRMED,
        ),
        diagnostics={
            "prepared_audio_artifact_uri": "campaign-1/records/prepared/job-1.wav",
            "label_overlap_seconds": {"SPEAKER_00": 3.5},
        },
    )

    mappings.save_many((record,))

    assert mappings.list_for_job(ProcessingJobId("job-1")) == (record,)
    assert mappings.list_for_transcript(TranscriptId("transcript-1")) == (record,)
    assert mappings.list_for_job(ProcessingJobId("missing")) == ()


def _database(tmp_path: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "notekeeper.sqlite3")
    database.initialize()
    return database


def _campaign() -> Campaign:
    metadata = AudioMetadata(
        duration_seconds=12,
        sample_rate_hz=16000,
        channels=1,
        checksum="checksum",
    )
    participant = Participant(
        id=ParticipantId("participant-1"),
        campaign_id=CampaignId("campaign-1"),
        display_name="Alice",
    )
    sample = VoiceSample(
        id=VoiceSampleId("sample-1"),
        campaign_id=CampaignId("campaign-1"),
        participant_id=participant.id,
        artifact=ArtifactRef(uri="campaign-1/players/Alice/sample.wav"),
        metadata=metadata,
    )
    audio_track = AudioTrack(
        id=AudioTrackId("audio-track-1"),
        campaign_id=CampaignId("campaign-1"),
        artifact=ArtifactRef(uri="campaign-1/records/session.wav"),
        metadata=metadata,
        title="Session",
    )
    return Campaign(
        id=CampaignId("campaign-1"),
        name="Campaign",
        participants=(participant,),
        voice_samples=(sample,),
        audio_tracks=(audio_track,),
    )
