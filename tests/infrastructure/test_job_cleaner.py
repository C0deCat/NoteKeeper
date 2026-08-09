from datetime import datetime
from pathlib import Path

from notekeeper.application import ProgressEvent, ProgressEventKind
from notekeeper.domain import CampaignId, JobStatus, ProcessingJob, ProgressBar
from notekeeper.infrastructure.cleanup import LocalJobCleaner
from notekeeper.infrastructure.filesystem import LocalCampaignArtifactStorage
from notekeeper.infrastructure.sqlite import (
    SQLiteDatabase,
    SQLiteJobRepository,
    SQLiteProgressEventSnapshotStore,
)


def test_job_cleaner_deletes_progress_snapshot(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "notekeeper.sqlite3")
    database.initialize()
    jobs = SQLiteJobRepository(database)
    snapshots = SQLiteProgressEventSnapshotStore(database)
    job = ProcessingJob(
        id="job-1",
        campaign_id=CampaignId("campaign-1"),
        audio_track_id="audio-track-1",
        status=JobStatus.FAILED,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        error_message="failed",
    )
    snapshot = ProgressEvent(
        operation_id=str(job.id),
        stage_index=1,
        stage_count=1,
        timing_available=True,
        kind=ProgressEventKind.FAILED,
        progress=ProgressBar(stage="transcribing"),
    )
    jobs.save(job)
    snapshots.save(snapshot)
    cleaner = LocalJobCleaner(
        database,
        LocalCampaignArtifactStorage(tmp_path / "artifacts"),
        tmp_path / "work",
    )

    assert cleaner.clean(job.campaign_id, (job,)) == (job.id,)
    assert jobs.get(job.id) is None
    assert snapshots.get(str(job.id)) is None
