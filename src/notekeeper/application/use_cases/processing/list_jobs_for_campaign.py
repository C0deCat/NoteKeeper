"""List processing jobs for a campaign use case."""

from notekeeper.application.commands import ListJobsForCampaignCommand
from notekeeper.application.ports import CampaignRepository, JobRepository
from notekeeper.application.results import ListJobsForCampaignResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId


class ListJobsForCampaign:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        job_repository: JobRepository,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._job_repository = job_repository

    def execute(
        self,
        command: ListJobsForCampaignCommand,
    ) -> ListJobsForCampaignResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        return ListJobsForCampaignResult(
            jobs=self._job_repository.list_for_campaign(campaign.id),
        )
