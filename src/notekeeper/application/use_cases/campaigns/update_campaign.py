"""Update campaign use case."""

from dataclasses import replace

from notekeeper.application.commands import UpdateCampaignCommand
from notekeeper.application.ports import CampaignRepository
from notekeeper.application.results import UpdateCampaignResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId


class UpdateCampaign:
    def __init__(self, campaign_repository: CampaignRepository) -> None:
        self._campaign_repository = campaign_repository

    def execute(self, command: UpdateCampaignCommand) -> UpdateCampaignResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        updated_campaign = replace(campaign, name=command.name)
        self._campaign_repository.save(updated_campaign)
        return UpdateCampaignResult(campaign=updated_campaign)
