"""Update campaign-specific recap guidances."""

from notekeeper.application.commands import UpdateRecapGuidancesCommand
from notekeeper.application.errors import InvalidOperationError
from notekeeper.application.ports import CampaignRepository, RecapGuidances
from notekeeper.application.results import UpdateRecapGuidancesResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId


class UpdateRecapGuidances:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        recap_guidances: RecapGuidances,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._recap_guidances = recap_guidances

    def execute(
        self,
        command: UpdateRecapGuidancesCommand,
    ) -> UpdateRecapGuidancesResult:
        campaign_id = CampaignId(command.campaign_id)
        _require_campaign(self._campaign_repository, campaign_id)
        if (
            command.chunk_recap_guidances is None
            and command.combined_recap_guidances is None
        ):
            raise InvalidOperationError("at least one recap guidance is required")

        chunk_guidance = self._updated_or_current(
            command.chunk_recap_guidances,
            self._recap_guidances.get_chunk_recap_guidances(campaign_id),
            "chunk recap guidance",
        )
        combined_guidance = self._updated_or_current(
            command.combined_recap_guidances,
            self._recap_guidances.get_combined_recap_guidances(campaign_id),
            "combined recap guidance",
        )
        self._recap_guidances.save_recap_guidances(
            campaign_id,
            chunk_recap_guidances=chunk_guidance,
            combined_recap_guidances=combined_guidance,
        )
        return UpdateRecapGuidancesResult(
            campaign_id=str(campaign_id),
            chunk_recap_guidances=chunk_guidance,
            combined_recap_guidances=combined_guidance,
        )

    @staticmethod
    def _updated_or_current(
        updated: str | None,
        current: str,
        field: str,
    ) -> str:
        if updated is None:
            return current
        if not updated.strip():
            raise InvalidOperationError(f"{field} must not be empty")
        return updated
