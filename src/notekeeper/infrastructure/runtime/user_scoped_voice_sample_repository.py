"""Voice sample repository scoped through campaign ownership."""

from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import VoiceSampleRepository
from notekeeper.domain import CampaignId, ParticipantId, VoiceSample, VoiceSampleId

from .user_campaign_access import UserCampaignAccess


class UserScopedVoiceSampleRepository(VoiceSampleRepository):
    def __init__(self, repository: VoiceSampleRepository, access: UserCampaignAccess) -> None:
        self._repository = repository
        self._access = access

    def get(self, voice_sample_id: VoiceSampleId) -> VoiceSample | None:
        value = self._repository.get(voice_sample_id)
        return value if value is not None and self._access.allows(value.campaign_id) else None

    def get_by_artifact_uri(self, campaign_id: CampaignId, artifact_uri: str) -> VoiceSample | None:
        if not self._access.allows(campaign_id):
            return None
        return self._repository.get_by_artifact_uri(campaign_id, artifact_uri)

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[VoiceSample, ...]:
        self._access.require(campaign_id)
        return self._repository.list_for_campaign(campaign_id)

    def list_for_participant(self, participant_id: ParticipantId) -> tuple[VoiceSample, ...]:
        values = self._repository.list_for_participant(participant_id)
        return tuple(value for value in values if self._access.allows(value.campaign_id))

    def save(self, voice_sample: VoiceSample) -> None:
        self._access.require(voice_sample.campaign_id)
        self._repository.save(voice_sample)

    def delete(self, voice_sample_id: VoiceSampleId) -> None:
        value = self.get(voice_sample_id)
        if value is None:
            raise NotFoundError(f"voice sample {voice_sample_id} was not found")
        self._repository.delete(voice_sample_id)


__all__ = ["UserScopedVoiceSampleRepository"]
