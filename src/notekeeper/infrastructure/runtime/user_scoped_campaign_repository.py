"""Campaign repository scoped to the current user."""

from notekeeper.application.ports import CampaignRepository
from notekeeper.domain import Campaign, CampaignId

from .user_campaign_access import UserCampaignAccess


class UserScopedCampaignRepository(CampaignRepository):
    def __init__(self, repository: CampaignRepository, access: UserCampaignAccess) -> None:
        self._repository = repository
        self._access = access

    def get(self, campaign_id: CampaignId) -> Campaign | None:
        campaign = self._repository.get(campaign_id)
        if campaign is None or campaign.owner_user_id != self._access.current_user_id():
            return None
        return campaign

    def list(self) -> tuple[Campaign, ...]:
        user_id = self._access.current_user_id()
        return tuple(
            campaign
            for campaign in self._repository.list()
            if campaign.owner_user_id == user_id
        )

    def save(self, campaign: Campaign) -> None:
        if campaign.owner_user_id != self._access.current_user_id():
            self._access.require(campaign.id)
        existing = self._repository.get(campaign.id)
        if existing is not None and existing.owner_user_id != campaign.owner_user_id:
            self._access.require(campaign.id)
        self._repository.save(campaign)

    def delete(self, campaign_id: CampaignId) -> None:
        self._access.require(campaign_id)
        self._repository.delete(campaign_id)


__all__ = ["UserScopedCampaignRepository"]
