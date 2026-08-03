"""Processing-job repository decorator that invalidates dashboard views."""

from notekeeper.application.ports import DashboardEventPublisher, JobRepository
from notekeeper.application.results import (
    DashboardChangedEvent,
    DashboardRefreshScope,
)
from notekeeper.domain import (
    AudioTrackId,
    CampaignId,
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
)


class EventPublishingJobRepository(JobRepository):
    def __init__(
        self,
        repository: JobRepository,
        events: DashboardEventPublisher,
    ) -> None:
        self._repository = repository
        self._events = events

    def get(self, job_id: ProcessingJobId) -> ProcessingJob | None:
        return self._repository.get(job_id)

    def list_for_campaign(
        self,
        campaign_id: CampaignId,
    ) -> tuple[ProcessingJob, ...]:
        return self._repository.list_for_campaign(campaign_id)

    def list_for_audio_track(
        self,
        audio_track_id: AudioTrackId,
    ) -> tuple[ProcessingJob, ...]:
        return self._repository.list_for_audio_track(audio_track_id)

    def save(self, job: ProcessingJob) -> None:
        self._repository.save(job)
        self._publish(job)

    def save_if_status(
        self,
        job: ProcessingJob,
        expected_status: JobStatus,
    ) -> bool:
        saved = self._repository.save_if_status(job, expected_status)
        if saved:
            self._publish(job)
        return saved

    def delete(self, job_id: ProcessingJobId) -> None:
        job = self._repository.get(job_id)
        self._repository.delete(job_id)
        if job is not None:
            self._publish(job)

    def _publish(self, job: ProcessingJob) -> None:
        self._events.publish(
            DashboardChangedEvent(
                campaign_id=str(job.campaign_id),
                scope=DashboardRefreshScope.CAMPAIGN_CONTENT,
            ),
        )


__all__ = ["EventPublishingJobRepository"]
