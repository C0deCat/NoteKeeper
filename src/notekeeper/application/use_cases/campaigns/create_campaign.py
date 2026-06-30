"""Create campaign use case."""

from notekeeper.application.commands import CreateCampaignCommand
from notekeeper.application.ports import CampaignRepository, IdGenerator
from notekeeper.application.results import CreateCampaignResult
from notekeeper.domain import Campaign, CampaignId


class CreateCampaign:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        id_generator: IdGenerator,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._id_generator = id_generator

    def execute(self, command: CreateCampaignCommand) -> CreateCampaignResult:
        campaign = Campaign(
            id=CampaignId(self._id_generator.campaign_id()),
            name=command.name,
        )
        self._campaign_repository.save(campaign)
        return CreateCampaignResult(campaign=campaign)
