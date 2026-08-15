"""Audio track repository scoped through campaign ownership."""

from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import AudioTrackRepository
from notekeeper.domain import AudioTrack, AudioTrackId, CampaignId

from .user_campaign_access import UserCampaignAccess


class UserScopedAudioTrackRepository(AudioTrackRepository):
    def __init__(self, repository: AudioTrackRepository, access: UserCampaignAccess) -> None:
        self._repository = repository
        self._access = access

    def get(self, audio_track_id: AudioTrackId) -> AudioTrack | None:
        value = self._repository.get(audio_track_id)
        return value if value is not None and self._access.allows(value.campaign_id) else None

    def get_by_artifact_uri(self, campaign_id: CampaignId, artifact_uri: str) -> AudioTrack | None:
        if not self._access.allows(campaign_id):
            return None
        return self._repository.get_by_artifact_uri(campaign_id, artifact_uri)

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[AudioTrack, ...]:
        self._access.require(campaign_id)
        return self._repository.list_for_campaign(campaign_id)

    def save(self, audio_track: AudioTrack) -> None:
        self._access.require(audio_track.campaign_id)
        self._repository.save(audio_track)

    def delete(self, audio_track_id: AudioTrackId) -> None:
        value = self.get(audio_track_id)
        if value is None:
            raise NotFoundError(f"audio track {audio_track_id} was not found")
        self._repository.delete(audio_track_id)


__all__ = ["UserScopedAudioTrackRepository"]
