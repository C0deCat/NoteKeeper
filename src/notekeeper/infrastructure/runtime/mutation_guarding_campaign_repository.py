"""Campaign repository decorator enforcing the active-job mutation policy."""

from notekeeper.application.ports import CampaignRepository
from notekeeper.application.use_cases.utils import CampaignMutationPolicy
from notekeeper.domain import Campaign, CampaignId


class MutationGuardingCampaignRepository(CampaignRepository):
    def __init__(
        self,
        repository: CampaignRepository,
        policy: CampaignMutationPolicy,
    ) -> None:
        self._repository = repository
        self._policy = policy

    def get(self, campaign_id: CampaignId) -> Campaign | None:
        return self._repository.get(campaign_id)

    def list(self) -> tuple[Campaign, ...]:
        return self._repository.list()

    def save(self, campaign: Campaign) -> None:
        with self._policy.mutation(campaign.id):
            self._repository.save(campaign)

    def delete(self, campaign_id: CampaignId) -> None:
        with self._policy.mutation(campaign_id):
            self._repository.delete(campaign_id)


__all__ = ["MutationGuardingCampaignRepository"]
