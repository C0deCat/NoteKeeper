"""Delete campaign use case."""

from notekeeper.application.commands import DeleteCampaignCommand
from notekeeper.application.ports import CampaignRepository
from notekeeper.application.results import DeleteCampaignResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId


class DeleteCampaign:
    def __init__(self, campaign_repository: CampaignRepository) -> None:
        self._campaign_repository = campaign_repository

    def execute(self, command: DeleteCampaignCommand) -> DeleteCampaignResult:
        campaign_id = CampaignId(command.campaign_id)
        _require_campaign(self._campaign_repository, campaign_id)
        self._campaign_repository.delete(campaign_id)
        return DeleteCampaignResult(campaign_id=command.campaign_id)
