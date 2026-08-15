"""Recap repository scoped through its transcript campaign."""

from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import RecapRepository, TranscriptRepository
from notekeeper.domain import Recap, RecapId, TranscriptId

from .user_campaign_access import UserCampaignAccess


class UserScopedRecapRepository(RecapRepository):
    def __init__(
        self,
        repository: RecapRepository,
        transcripts: TranscriptRepository,
        access: UserCampaignAccess,
    ) -> None:
        self._repository = repository
        self._transcripts = transcripts
        self._access = access

    def get(self, recap_id: RecapId) -> Recap | None:
        value = self._repository.get(recap_id)
        return value if value is not None and self._allows_transcript(value.transcript_id) else None

    def list_for_transcript(self, transcript_id: TranscriptId) -> tuple[Recap, ...]:
        if not self._allows_transcript(transcript_id):
            return ()
        return self._repository.list_for_transcript(transcript_id)

    def save(self, recap: Recap) -> None:
        if not self._allows_transcript(recap.transcript_id):
            raise NotFoundError(f"transcript {recap.transcript_id} was not found")
        self._repository.save(recap)

    def delete(self, recap_id: RecapId) -> None:
        if self.get(recap_id) is None:
            raise NotFoundError(f"recap {recap_id} was not found")
        self._repository.delete(recap_id)

    def _allows_transcript(self, transcript_id: TranscriptId) -> bool:
        transcript = self._transcripts.get(transcript_id)
        return transcript is not None and self._access.allows(transcript.campaign_id)


__all__ = ["UserScopedRecapRepository"]
