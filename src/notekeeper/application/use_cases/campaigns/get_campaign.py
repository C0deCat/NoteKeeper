"""Get campaign use case."""

from notekeeper.application.commands import GetCampaignCommand
from notekeeper.application.ports import CampaignRepository
from notekeeper.application.results import GetCampaignResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId


class GetCampaign:
    def __init__(self, campaign_repository: CampaignRepository) -> None:
        self._campaign_repository = campaign_repository

    def execute(self, command: GetCampaignCommand) -> GetCampaignResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        return GetCampaignResult(campaign=campaign)
