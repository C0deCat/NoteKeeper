"""Create campaign use case."""

from notekeeper.application.commands import CreateCampaignCommand
from notekeeper.application.ports import (
    CampaignArtifactStorage,
    CampaignRepository,
    IdGenerator,
)
from notekeeper.application.results import CreateCampaignResult
from notekeeper.domain import Campaign, CampaignId


class CreateCampaign:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        id_generator: IdGenerator,
        artifact_storage: CampaignArtifactStorage | None = None,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._id_generator = id_generator
        self._artifact_storage = artifact_storage

    def execute(self, command: CreateCampaignCommand) -> CreateCampaignResult:
        campaign = Campaign(
            id=CampaignId(self._id_generator.campaign_id()),
            name=command.name,
        )
        if self._artifact_storage is not None:
            self._artifact_storage.ensure_campaign_layout(campaign.id)
        self._campaign_repository.save(campaign)
        return CreateCampaignResult(campaign=campaign)
