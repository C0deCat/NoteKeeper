"""Processing-job cleaner decorator that invalidates dashboard views."""

from notekeeper.application.ports import DashboardEventPublisher, JobCleaner
from notekeeper.application.results import (
    DashboardChangedEvent,
    DashboardRefreshScope,
)
from notekeeper.domain import CampaignId, ProcessingJob, ProcessingJobId


class EventPublishingJobCleaner(JobCleaner):
    def __init__(
        self,
        cleaner: JobCleaner,
        events: DashboardEventPublisher,
    ) -> None:
        self._cleaner = cleaner
        self._events = events

    def clean(
        self,
        campaign_id: CampaignId,
        jobs: tuple[ProcessingJob, ...],
    ) -> tuple[ProcessingJobId, ...]:
        deleted_ids = self._cleaner.clean(campaign_id, jobs)
        if deleted_ids:
            self._events.publish(
                DashboardChangedEvent(
                    campaign_id=str(campaign_id),
                    scope=DashboardRefreshScope.CAMPAIGN_CONTENT,
                ),
            )
        return deleted_ids


__all__ = ["EventPublishingJobCleaner"]
