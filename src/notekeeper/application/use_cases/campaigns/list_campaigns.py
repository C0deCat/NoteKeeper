"""List campaigns use case."""

from notekeeper.application.commands import ListCampaignsCommand
from notekeeper.application.ports import CampaignRepository
from notekeeper.application.results import ListCampaignsResult


class ListCampaigns:
    def __init__(self, campaign_repository: CampaignRepository) -> None:
        self._campaign_repository = campaign_repository

    def execute(self, command: ListCampaignsCommand) -> ListCampaignsResult:
        return ListCampaignsResult(campaigns=self._campaign_repository.list())
