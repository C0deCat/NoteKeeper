"""Participant repository scoped through campaign ownership."""

from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import ParticipantRepository
from notekeeper.domain import CampaignId, Participant, ParticipantId

from .user_campaign_access import UserCampaignAccess


class UserScopedParticipantRepository(ParticipantRepository):
    def __init__(self, repository: ParticipantRepository, access: UserCampaignAccess) -> None:
        self._repository = repository
        self._access = access

    def get(self, participant_id: ParticipantId) -> Participant | None:
        value = self._repository.get(participant_id)
        return value if value is not None and self._access.allows(value.campaign_id) else None

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[Participant, ...]:
        self._access.require(campaign_id)
        return self._repository.list_for_campaign(campaign_id)

    def save(self, participant: Participant) -> None:
        self._access.require(participant.campaign_id)
        self._repository.save(participant)

    def delete(self, participant_id: ParticipantId) -> None:
        value = self.get(participant_id)
        if value is None:
            raise NotFoundError(f"participant {participant_id} was not found")
        self._repository.delete(participant_id)


__all__ = ["UserScopedParticipantRepository"]
