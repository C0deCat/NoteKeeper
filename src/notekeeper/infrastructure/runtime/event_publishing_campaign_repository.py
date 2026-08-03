"""Campaign repository decorator that invalidates dashboard views."""

from notekeeper.application.ports import (
    CampaignRepository,
    DashboardEventPublisher,
)
from notekeeper.application.results import (
    DashboardChangedEvent,
    DashboardRefreshScope,
)
from notekeeper.domain import Campaign, CampaignId


class EventPublishingCampaignRepository(CampaignRepository):
    def __init__(
        self,
        repository: CampaignRepository,
        events: DashboardEventPublisher,
    ) -> None:
        self._repository = repository
        self._events = events

    def get(self, campaign_id: CampaignId) -> Campaign | None:
        return self._repository.get(campaign_id)

    def list(self) -> tuple[Campaign, ...]:
        return self._repository.list()

    def save(self, campaign: Campaign) -> None:
        previous = self._repository.get(campaign.id)
        self._repository.save(campaign)
        scope = (
            DashboardRefreshScope.CAMPAIGN_LIST
            if previous is None or previous.name != campaign.name
            else DashboardRefreshScope.CAMPAIGN_CONTENT
        )
        self._events.publish(
            DashboardChangedEvent(
                campaign_id=str(campaign.id),
                scope=scope,
            ),
        )

    def delete(self, campaign_id: CampaignId) -> None:
        self._repository.delete(campaign_id)
        self._events.publish(
            DashboardChangedEvent(
                campaign_id=str(campaign_id),
                scope=DashboardRefreshScope.CAMPAIGN_LIST,
            ),
        )


__all__ = ["EventPublishingCampaignRepository"]
