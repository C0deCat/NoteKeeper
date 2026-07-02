"""Campaign job helpers."""

from notekeeper.application.ports import JobRepository
from notekeeper.domain import AudioTrackId, JobStatus


def delete_pending_jobs(
    job_repository: JobRepository,
    audio_track_id: AudioTrackId,
) -> int:
    deleted = 0
    for job in job_repository.list_for_audio_track(audio_track_id):
        if job.status is JobStatus.PENDING:
            job_repository.delete(job.id)
            deleted += 1
    return deleted
