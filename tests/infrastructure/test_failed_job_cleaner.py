from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from notekeeper.application import SpeakerMappingRecord
from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrack,
    Campaign,
    CampaignId,
    JobStatus,
    ParticipantId,
    ProcessingJob,
    ProcessingJobId,
    Recap,
    RecapId,
    SpeakerLabel,
    SpeakerMapping,
    SpeakerMappingSource,
    SpeakerMappingStatus,
    Transcript,
    TranscriptId,
)
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.cleanup import LocalFailedJobCleaner
from notekeeper.infrastructure.filesystem import LocalCampaignArtifactStorage
from notekeeper.infrastructure.sqlite import (
    SQLiteCampaignRepository,
    SQLiteDatabase,
    SQLiteJobRepository,
    SQLiteRecapRepository,
    SQLiteSpeakerMappingRepository,
    SQLiteTranscriptRepository,
)


def test_failed_job_cleaner_removes_owned_data_and_preserves_other_data(
    tmp_path: Path,
) -> None:
    context = _CleanupContext(tmp_path)
    failed = context.save_job(
        "job-failed",
        JobStatus.FAILED,
        transcript_id="transcript-failed",
        recap_id="recap-failed",
    )
    pending = context.save_job("job-pending", JobStatus.PENDING)
    other_campaign_job = context.save_job(
        "job-other",
        JobStatus.FAILED,
        campaign_id="campaign-2",
    )
    transcript, recap = context.save_transcript_and_recap(
        "transcript-failed",
        "recap-failed",
    )
    context.save_mapping(failed, transcript)
    paths = context.create_job_files(failed, transcript, recap)

    deleted_ids = context.cleaner.clean(context.campaign.id, (failed,))

    assert deleted_ids == (failed.id,)
    assert context.jobs.get(failed.id) is None
    assert context.jobs.get(pending.id) == pending
    assert context.jobs.get(other_campaign_job.id) == other_campaign_job
    assert context.transcripts.get(transcript.id) == transcript
    assert context.recaps.get(recap.id) == recap
    assert context.mappings.list_for_job(failed.id) == ()
    assert all(not path.exists() for path in paths["deleted"])
    assert all(path.exists() for path in paths["preserved"])


def test_failed_job_cleaner_preserves_shared_transcript_and_recap(
    tmp_path: Path,
) -> None:
    context = _CleanupContext(tmp_path)
    transcript, recap = context.save_transcript_and_recap(
        "transcript-shared",
        "recap-shared",
    )
    failed = context.save_job(
        "job-failed",
        JobStatus.FAILED,
        transcript_id=str(transcript.id),
        recap_id=str(recap.id),
    )
    completed = context.save_job(
        "job-completed",
        JobStatus.COMPLETED,
        transcript_id=str(transcript.id),
        recap_id=str(recap.id),
    )
    context.save_mapping(failed, transcript)
    context.save_mapping(completed, transcript)

    context.cleaner.clean(context.campaign.id, (failed,))

    assert context.jobs.get(failed.id) is None
    assert context.jobs.get(completed.id) == completed
    assert context.transcripts.get(transcript.id) == transcript
    assert context.recaps.get(recap.id) == recap
    assert context.mappings.list_for_job(failed.id) == ()
    assert context.mappings.list_for_job(completed.id)


def test_failed_job_cleaner_preserves_transcript_used_by_external_recap(
    tmp_path: Path,
) -> None:
    context = _CleanupContext(tmp_path)
    transcript, recap = context.save_transcript_and_recap(
        "transcript-shared",
        "recap-shared",
    )
    failed = context.save_job(
        "job-failed",
        JobStatus.FAILED,
        transcript_id=str(transcript.id),
        recap_id=str(recap.id),
    )
    completed = context.save_job(
        "job-completed",
        JobStatus.COMPLETED,
        recap_id=str(recap.id),
    )

    context.cleaner.clean(context.campaign.id, (failed,))

    assert context.jobs.get(completed.id) == completed
    assert context.transcripts.get(transcript.id) == transcript
    assert context.recaps.get(recap.id) == recap


def test_failed_job_cleaner_keeps_database_rows_when_file_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _CleanupContext(tmp_path)
    failed = context.save_job("job-failed", JobStatus.FAILED)

    def fail_remove(path: Path, root: Path) -> None:
        raise InfrastructureError("file cleanup failed")

    monkeypatch.setattr(context.cleaner, "_remove_path", fail_remove)

    with pytest.raises(InfrastructureError, match="file cleanup failed"):
        context.cleaner.clean(context.campaign.id, (failed,))

    assert context.jobs.get(failed.id) == failed


def test_failed_job_cleaner_rolls_back_database_transaction(
    tmp_path: Path,
) -> None:
    context = _CleanupContext(tmp_path)
    failed = context.save_job(
        "job-failed",
        JobStatus.FAILED,
        transcript_id="transcript-failed",
        recap_id="recap-failed",
    )
    transcript, recap = context.save_transcript_and_recap(
        "transcript-failed",
        "recap-failed",
    )
    context.save_mapping(failed, transcript)
    with context.database.connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER block_failed_job_delete
            BEFORE DELETE ON jobs
            WHEN OLD.id = 'job-failed'
            BEGIN
                SELECT RAISE(ABORT, 'blocked');
            END
            """,
        )

    with pytest.raises(
        InfrastructureError,
        match="could not delete processing jobs from the database",
    ):
        context.cleaner.clean(context.campaign.id, (failed,))

    assert context.jobs.get(failed.id) == failed
    with context.database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM transcripts WHERE id = ?",
            (str(transcript.id),),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM recaps WHERE id = ?",
            (str(recap.id),),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM speaker_mappings WHERE job_id = ?",
            (str(failed.id),),
        ).fetchone()[0] == 1


class _CleanupContext:
    def __init__(self, tmp_path: Path) -> None:
        self.database = SQLiteDatabase(tmp_path / "notekeeper.sqlite3")
        self.database.initialize()
        self.storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
        self.work_root = tmp_path / "work"
        self.campaigns = SQLiteCampaignRepository(self.database)
        self.jobs = SQLiteJobRepository(self.database)
        self.transcripts = SQLiteTranscriptRepository(self.database, self.storage)
        self.recaps = SQLiteRecapRepository(self.database, self.storage)
        self.mappings = SQLiteSpeakerMappingRepository(self.database)
        self.campaign = _campaign("campaign-1")
        self.other_campaign = _campaign("campaign-2")
        self.campaigns.save(self.campaign)
        self.campaigns.save(self.other_campaign)
        self.cleaner = LocalFailedJobCleaner(
            self.database,
            self.storage,
            self.work_root,
        )

    def save_job(
        self,
        job_id: str,
        status: JobStatus,
        *,
        campaign_id: str = "campaign-1",
        transcript_id: str | None = None,
        recap_id: str | None = None,
    ) -> ProcessingJob:
        job = ProcessingJob(
            id=ProcessingJobId(job_id),
            campaign_id=CampaignId(campaign_id),
            audio_track_id=f"audio-{campaign_id}",
            status=status,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 2),
            transcript_id=(
                TranscriptId(transcript_id) if transcript_id is not None else None
            ),
            recap_id=RecapId(recap_id) if recap_id is not None else None,
            error_message="failed" if status is JobStatus.FAILED else None,
        )
        self.jobs.save(job)
        return job

    def save_transcript_and_recap(
        self,
        transcript_id: str,
        recap_id: str,
    ) -> tuple[Transcript, Recap]:
        transcript = Transcript(
            id=TranscriptId(transcript_id),
            campaign_id=self.campaign.id,
            audio_track_id=self.campaign.audio_tracks[0].id,
        )
        self.transcripts.save(transcript)
        recap = Recap(
            id=RecapId(recap_id),
            transcript_id=transcript.id,
            markdown="# Recap",
        )
        self.recaps.save(recap)
        return transcript, recap

    def save_mapping(self, job: ProcessingJob, transcript: Transcript) -> None:
        self.mappings.save_many(
            (
                SpeakerMappingRecord(
                    job_id=job.id,
                    transcript_id=transcript.id,
                    mapping=SpeakerMapping(
                        anonymous_label=SpeakerLabel.anonymous("SPEAKER_00"),
                        named_label=SpeakerLabel.named("Alice"),
                        participant_id=ParticipantId("participant-1"),
                        confidence=None,
                        source=SpeakerMappingSource.AUTOMATIC,
                        status=SpeakerMappingStatus.CONFIRMED,
                    ),
                    diagnostics={},
                ),
            ),
        )

    def create_job_files(
        self,
        job: ProcessingJob,
        transcript: Transcript,
        recap: Recap,
    ) -> dict[str, tuple[Path, ...]]:
        transient = self.storage.path_for_uri(
            f"{self.campaign.id}/records/transient/{job.id}",
        )
        transient.mkdir(parents=True)
        (transient / "prepared.wav").write_bytes(b"audio")
        manifest = self.storage.path_for_uri(
            f"{self.campaign.id}/records/manifests/{job.id}",
        )
        manifest.mkdir(parents=True)
        (manifest / "prepared-audio.json").write_text(
            "{}",
            encoding="utf-8",
        )
        work = self.work_root / str(self.campaign.id) / str(job.id)
        work.mkdir(parents=True)
        (work / "concat.txt").write_text("work", encoding="utf-8")
        raw = self.storage.path_for_uri(
            f"{self.campaign.id}/transcripts/raw-whisperx/{transcript.id}.json",
        )
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text("{}", encoding="utf-8")
        orphan_raw = self.storage.path_for_uri(
            f"{self.campaign.id}/transcripts/raw-whisperx/orphan.json",
        )
        orphan_raw.write_text(
            json.dumps(
                {
                    "audio_artifact": {
                        "uri": (
                            f"{self.campaign.id}/records/transient/"
                            f"{job.id}/prepared.wav"
                        ),
                    },
                },
            ),
            encoding="utf-8",
        )
        transcript_export = self.storage.path_for_uri(
            f"transcript-{transcript.id}.md",
        )
        transcript_export.write_text("transcript", encoding="utf-8")
        recap_export = self.storage.path_for_uri(f"recap-{recap.id}.md")
        recap_export.write_text("recap", encoding="utf-8")
        diagnostics = self.storage.path_for_uri(
            f"{self.campaign.id}/recaps/llm-diagnostics/recap-attempt",
        )
        diagnostics.mkdir(parents=True)
        (diagnostics / "attempt.json").write_text(
            json.dumps({"context": {"job_id": str(job.id)}}),
            encoding="utf-8",
        )
        source_recording = self.storage.path_for_uri(
            f"{self.campaign.id}/records/normalized/audio-1.wav",
        )
        source_recording.parent.mkdir(parents=True, exist_ok=True)
        source_recording.write_bytes(b"source")
        other_campaign_file = self.storage.path_for_uri(
            (
                f"{self.other_campaign.id}/records/transient/"
                "job-other/prepared.wav"
            ),
        )
        other_campaign_file.parent.mkdir(parents=True, exist_ok=True)
        other_campaign_file.write_bytes(b"other")
        transcript_payload = self.storage.path_for_uri(
            self.transcripts.payload_uri(transcript.id) or "",
        )
        recap_payload = self.storage.path_for_uri(
            self.recaps.payload_uri(recap.id) or "",
        )
        return {
            "deleted": (
                transient,
                manifest,
                work,
            ),
            "preserved": (
                raw,
                orphan_raw,
                transcript_export,
                recap_export,
                diagnostics,
                transcript_payload,
                recap_payload,
                source_recording,
                other_campaign_file,
            ),
        }


def _campaign(campaign_id: str) -> Campaign:
    audio_track = AudioTrack(
        id=f"audio-{campaign_id}",
        campaign_id=CampaignId(campaign_id),
        artifact=ArtifactRef(
            uri=f"{campaign_id}/records/normalized/audio-{campaign_id}.wav",
        ),
        metadata=AudioMetadata(duration_seconds=12),
    )
    return Campaign(
        id=CampaignId(campaign_id),
        name=campaign_id,
        audio_tracks=(audio_track,),
    )
