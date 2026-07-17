"""Clear failed processing jobs and their owned artifacts."""

from notekeeper.application.commands import ClearFailedJobsForCampaignCommand
from notekeeper.application.ports import (
    CampaignRepository,
    FailedJobCleaner,
    JobRepository,
)
from notekeeper.application.results import ClearFailedJobsForCampaignResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId, JobStatus


class ClearFailedJobsForCampaign:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        job_repository: JobRepository,
        failed_job_cleaner: FailedJobCleaner,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._job_repository = job_repository
        self._failed_job_cleaner = failed_job_cleaner

    def execute(
        self,
        command: ClearFailedJobsForCampaignCommand,
    ) -> ClearFailedJobsForCampaignResult:
        campaign_id = CampaignId(command.campaign_id)
        _require_campaign(self._campaign_repository, campaign_id)
        failed_jobs = tuple(
            job
            for job in self._job_repository.list_for_campaign(campaign_id)
            if job.status is JobStatus.FAILED
        )
        if not failed_jobs:
            return ClearFailedJobsForCampaignResult(deleted_job_ids=())

        deleted_job_ids = self._failed_job_cleaner.clean(campaign_id, failed_jobs)
        return ClearFailedJobsForCampaignResult(
            deleted_job_ids=tuple(str(job_id) for job_id in deleted_job_ids),
        )
