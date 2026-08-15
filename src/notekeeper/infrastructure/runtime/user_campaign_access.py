"""Campaign ownership checks for a current application user."""

from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import CampaignRepository, CurrentUserProvider
from notekeeper.domain import CampaignId, UserId


class UserCampaignAccess:
    def __init__(
        self,
        campaigns: CampaignRepository,
        current_user: CurrentUserProvider,
    ) -> None:
        self._campaigns = campaigns
        self._current_user = current_user

    def current_user_id(self) -> UserId:
        return self._current_user.require_user_id()

    def allows(self, campaign_id: CampaignId) -> bool:
        campaign = self._campaigns.get(campaign_id)
        return (
            campaign is not None
            and campaign.owner_user_id == self.current_user_id()
        )

    def require(self, campaign_id: CampaignId) -> None:
        if not self.allows(campaign_id):
            raise NotFoundError(f"campaign {campaign_id} was not found")


__all__ = ["UserCampaignAccess"]
