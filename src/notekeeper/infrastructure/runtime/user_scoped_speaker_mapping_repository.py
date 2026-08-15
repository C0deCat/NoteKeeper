"""Speaker mapping repository scoped through processing jobs."""

from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import JobRepository, SpeakerMappingRepository
from notekeeper.application.results import SpeakerMappingRecord
from notekeeper.domain import ProcessingJobId, TranscriptId

from .user_campaign_access import UserCampaignAccess


class UserScopedSpeakerMappingRepository(SpeakerMappingRepository):
    def __init__(
        self,
        repository: SpeakerMappingRepository,
        jobs: JobRepository,
        access: UserCampaignAccess,
    ) -> None:
        self._repository = repository
        self._jobs = jobs
        self._access = access

    def save_many(self, records: tuple[SpeakerMappingRecord, ...]) -> None:
        for record in records:
            self._require_job(record.job_id)
        self._repository.save_many(records)

    def list_for_job(self, job_id: ProcessingJobId) -> tuple[SpeakerMappingRecord, ...]:
        if not self._allows_job(job_id):
            return ()
        return self._repository.list_for_job(job_id)

    def list_for_transcript(self, transcript_id: TranscriptId) -> tuple[SpeakerMappingRecord, ...]:
        return tuple(
            record
            for record in self._repository.list_for_transcript(transcript_id)
            if self._allows_job(record.job_id)
        )

    def _allows_job(self, job_id: ProcessingJobId) -> bool:
        job = self._jobs.get(job_id)
        return job is not None and self._access.allows(job.campaign_id)

    def _require_job(self, job_id: ProcessingJobId) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            raise NotFoundError(f"processing job {job_id} was not found")
        self._access.require(job.campaign_id)


__all__ = ["UserScopedSpeakerMappingRepository"]
