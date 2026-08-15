"""Transcript repository scoped through campaign ownership."""

from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import TranscriptRepository
from notekeeper.domain import AudioTrackId, Transcript, TranscriptId

from .user_campaign_access import UserCampaignAccess


class UserScopedTranscriptRepository(TranscriptRepository):
    def __init__(self, repository: TranscriptRepository, access: UserCampaignAccess) -> None:
        self._repository = repository
        self._access = access

    def get(self, transcript_id: TranscriptId) -> Transcript | None:
        value = self._repository.get(transcript_id)
        return value if value is not None and self._access.allows(value.campaign_id) else None

    def list_for_audio_track(self, audio_track_id: AudioTrackId) -> tuple[Transcript, ...]:
        values = self._repository.list_for_audio_track(audio_track_id)
        return tuple(value for value in values if self._access.allows(value.campaign_id))

    def save(self, transcript: Transcript) -> None:
        self._access.require(transcript.campaign_id)
        self._repository.save(transcript)

    def delete(self, transcript_id: TranscriptId) -> None:
        if self.get(transcript_id) is None:
            raise NotFoundError(f"transcript {transcript_id} was not found")
        self._repository.delete(transcript_id)


__all__ = ["UserScopedTranscriptRepository"]
