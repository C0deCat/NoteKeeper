"""Create campaign use case."""

from notekeeper.application.commands import CreateCampaignCommand
from notekeeper.application import AccessContext
from notekeeper.application.ports import (
    CampaignArtifactStorage,
    CampaignRepository,
    IdGenerator,
    RecapGuidances,
)
from notekeeper.application.results import CreateCampaignResult
from notekeeper.domain import BUILTIN_ROOT_WORKSPACE_ID, Campaign, CampaignId


class CreateCampaign:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        id_generator: IdGenerator,
        recap_guidances: RecapGuidances,
        artifact_storage: CampaignArtifactStorage | None = None,
        access: AccessContext | None = None,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._id_generator = id_generator
        self._recap_guidances = recap_guidances
        self._artifact_storage = artifact_storage
        self._access = access

    def execute(self, command: CreateCampaignCommand) -> CreateCampaignResult:
        campaign = Campaign(
            id=CampaignId(self._id_generator.campaign_id()),
            name=command.name,
            workspace_id=(
                self._access.workspace_id
                if self._access is not None
                else BUILTIN_ROOT_WORKSPACE_ID
            ),
        )
        if self._artifact_storage is not None:
            self._artifact_storage.ensure_campaign_layout(campaign.id)
        self._recap_guidances.get_chunk_recap_guidances(campaign.id)
        self._recap_guidances.get_combined_recap_guidances(campaign.id)
        self._campaign_repository.save(campaign)
        return CreateCampaignResult(campaign=campaign)
