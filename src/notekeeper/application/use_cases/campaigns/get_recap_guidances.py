"""Get campaign-specific recap guidances."""

from notekeeper.application.commands import GetRecapGuidancesCommand
from notekeeper.application.ports import CampaignRepository, RecapGuidances
from notekeeper.application.results import GetRecapGuidancesResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId


class GetRecapGuidances:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        recap_guidances: RecapGuidances,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._recap_guidances = recap_guidances

    def execute(
        self,
        command: GetRecapGuidancesCommand,
    ) -> GetRecapGuidancesResult:
        campaign_id = CampaignId(command.campaign_id)
        _require_campaign(self._campaign_repository, campaign_id)
        return GetRecapGuidancesResult(
            campaign_id=str(campaign_id),
            chunk_recap_guidances=(
                self._recap_guidances.get_chunk_recap_guidances(campaign_id)
            ),
            combined_recap_guidances=(
                self._recap_guidances.get_combined_recap_guidances(campaign_id)
            ),
        )
