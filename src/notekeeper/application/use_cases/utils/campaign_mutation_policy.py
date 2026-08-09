"""Serialize campaign writes against processing-job queue transitions."""

from contextlib import contextmanager
from collections.abc import Iterator

from notekeeper.application.errors import InvalidOperationError
from notekeeper.application.ports import CampaignMutationGuard, JobRepository
from notekeeper.domain import CampaignId, JobStatus


ACTIVE_CAMPAIGN_JOB_STATUSES = (
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.CANCELING,
    JobStatus.WAITING_FOR_REVIEW,
)


class CampaignMutationPolicy:
    def __init__(
        self,
        job_repository: JobRepository,
        guard: CampaignMutationGuard,
    ) -> None:
        self._job_repository = job_repository
        self._guard = guard

    @contextmanager
    def mutation(self, campaign_id: CampaignId) -> Iterator[None]:
        with self._guard.acquire(campaign_id):
            if self._job_repository.has_for_campaign_with_statuses(
                campaign_id,
                ACTIVE_CAMPAIGN_JOB_STATUSES,
            ):
                raise InvalidOperationError(
                    "campaign cannot be changed while processing jobs are active"
                )
            yield

    def queue_transition(self, campaign_id: CampaignId):
        return self._guard.acquire(campaign_id)


__all__ = ["ACTIVE_CAMPAIGN_JOB_STATUSES", "CampaignMutationPolicy"]
