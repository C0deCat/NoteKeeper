from __future__ import annotations

import wave
from datetime import datetime
from pathlib import Path

from notekeeper.application import SyncCampaignFolder, SyncCampaignFolderCommand
from notekeeper.domain import (
    AudioTrackId,
    Campaign,
    CampaignId,
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
    Recap,
    RecapId,
    SpeakerLabel,
    TimeRange,
    Transcript,
    TranscriptId,
    TranscriptSegment,
)
from notekeeper.infrastructure.filesystem import (
    LocalAudioMetadataReader,
    LocalCampaignArtifactStorage,
    LocalCampaignFolderScanner,
)
from notekeeper.infrastructure.sqlite import (
    SQLiteCampaignRepository,
    SQLiteDatabase,
    SQLiteJobRepository,
    SQLiteRecapRepository,
    SQLiteTranscriptRepository,
)


def test_sync_campaign_folder_with_sqlite_and_filesystem_preserves_outputs(
    tmp_path: Path,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    database = SQLiteDatabase(tmp_path / "notekeeper.sqlite3")
    database.initialize()
    campaigns = SQLiteCampaignRepository(database)
    jobs = SQLiteJobRepository(database)
    transcripts = SQLiteTranscriptRepository(database, storage)
    recaps = SQLiteRecapRepository(database, storage)
    storage.ensure_campaign_layout(CampaignId("campaign-1"))
    campaigns.save(Campaign(id=CampaignId("campaign-1"), name="Synced"))
    alice_path = tmp_path / "artifacts" / "campaign-1" / "players" / "Alice"
    alice_path.mkdir()
    sample_path = alice_path / "sample.wav"
    record_path = tmp_path / "artifacts" / "campaign-1" / "records" / "session.wav"
    _write_wav(sample_path)
    _write_wav(record_path)
    sync = SyncCampaignFolder(
        campaigns,
        jobs,
        LocalCampaignFolderScanner(storage),
        LocalAudioMetadataReader(storage, ffprobe_path="missing-ffprobe"),
        _Ids(),
    )

    first_result = sync.execute(SyncCampaignFolderCommand(campaign_id="campaign-1"))

    assert first_result.participants_created == 1
    assert first_result.voice_samples_added == 1
    assert first_result.audio_tracks_added == 1
    loaded = campaigns.get(CampaignId("campaign-1"))
    assert loaded is not None
    assert loaded.participants[0].display_name == "Alice"
    assert loaded.voice_samples[0].metadata.checksum is not None
    assert loaded.audio_tracks[0].metadata.file_size_bytes == record_path.stat().st_size

    audio_track_id = loaded.audio_tracks[0].id
    transcript = Transcript(
        id=TranscriptId("transcript-1"),
        campaign_id=loaded.id,
        audio_track_id=audio_track_id,
        segments=(
            TranscriptSegment(
                index=0,
                time_range=TimeRange(0, 1),
                speaker_label=SpeakerLabel.named("Alice"),
                text="Hello",
            ),
        ),
    )
    recap = Recap(
        id=RecapId("recap-1"),
        transcript_id=transcript.id,
        markdown="Done",
    )
    transcripts.save(transcript)
    recaps.save(recap)
    pending = ProcessingJob(
        id=ProcessingJobId("job-pending"),
        campaign_id=loaded.id,
        audio_track_id=audio_track_id,
        status=JobStatus.PENDING,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 1),
    )
    completed = ProcessingJob(
        id=ProcessingJobId("job-completed"),
        campaign_id=loaded.id,
        audio_track_id=audio_track_id,
        status=JobStatus.COMPLETED,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 1),
        transcript_id=transcript.id,
        recap_id=recap.id,
    )
    jobs.save(pending)
    jobs.save(completed)

    sample_path.unlink()
    record_path.unlink()
    second_result = sync.execute(SyncCampaignFolderCommand(campaign_id="campaign-1"))
    loaded_after_delete = campaigns.get(CampaignId("campaign-1"))

    assert second_result.voice_samples_deleted == 1
    assert second_result.audio_tracks_deleted == 1
    assert second_result.pending_jobs_deleted == 1
    assert loaded_after_delete is not None
    assert loaded_after_delete.participants[0].display_name == "Alice"
    assert loaded_after_delete.voice_samples == ()
    assert loaded_after_delete.audio_tracks == ()
    assert jobs.get(pending.id) is None
    assert jobs.get(completed.id) == completed
    assert transcripts.get(transcript.id) == transcript
    assert recaps.get(recap.id) == recap


class _Ids:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def participant_id(self) -> str:
        return self._next("participant")

    def voice_sample_id(self) -> str:
        return self._next("voice-sample")

    def audio_track_id(self) -> str:
        return self._next("audio-track")

    def campaign_id(self) -> str:
        return self._next("campaign")

    def processing_job_id(self) -> str:
        return self._next("job")

    def transcript_id(self) -> str:
        return self._next("transcript")

    def recap_id(self) -> str:
        return self._next("recap")

    def _next(self, prefix: str) -> str:
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        return f"{prefix}-{self._counts[prefix]}"


def _write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 1600)
