"""List campaign participants use case."""

from notekeeper.application.commands import ListParticipantsCommand
from notekeeper.application.ports import CampaignRepository
from notekeeper.application.results import ListParticipantsResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId


class ListParticipants:
    def __init__(self, campaign_repository: CampaignRepository) -> None:
        self._campaign_repository = campaign_repository

    def execute(self, command: ListParticipantsCommand) -> ListParticipantsResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        return ListParticipantsResult(participants=campaign.participants)
