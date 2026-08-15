"""Processing job repository scoped through campaign ownership."""

from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import JobRepository
from notekeeper.domain import (
    AudioTrackId,
    CampaignId,
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
)

from .user_campaign_access import UserCampaignAccess


class UserScopedJobRepository(JobRepository):
    def __init__(self, repository: JobRepository, access: UserCampaignAccess) -> None:
        self._repository = repository
        self._access = access

    def get(self, job_id: ProcessingJobId) -> ProcessingJob | None:
        value = self._repository.get(job_id)
        return value if value is not None and self._access.allows(value.campaign_id) else None

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[ProcessingJob, ...]:
        self._access.require(campaign_id)
        return self._repository.list_for_campaign(campaign_id)

    def list_for_audio_track(self, audio_track_id: AudioTrackId) -> tuple[ProcessingJob, ...]:
        return tuple(
            value
            for value in self._repository.list_for_audio_track(audio_track_id)
            if self._access.allows(value.campaign_id)
        )

    def list_by_statuses(self, statuses: tuple[JobStatus, ...]) -> tuple[ProcessingJob, ...]:
        return tuple(
            value
            for value in self._repository.list_by_statuses(statuses)
            if self._access.allows(value.campaign_id)
        )

    def has_for_campaign_with_statuses(self, campaign_id: CampaignId, statuses: tuple[JobStatus, ...]) -> bool:
        self._access.require(campaign_id)
        return self._repository.has_for_campaign_with_statuses(campaign_id, statuses)

    def save(self, job: ProcessingJob) -> None:
        self._access.require(job.campaign_id)
        self._repository.save(job)

    def save_if_status(self, job: ProcessingJob, expected_status: JobStatus) -> bool:
        self._access.require(job.campaign_id)
        return self._repository.save_if_status(job, expected_status)

    def delete(self, job_id: ProcessingJobId) -> None:
        if self.get(job_id) is None:
            raise NotFoundError(f"processing job {job_id} was not found")
        self._repository.delete(job_id)


__all__ = ["UserScopedJobRepository"]
