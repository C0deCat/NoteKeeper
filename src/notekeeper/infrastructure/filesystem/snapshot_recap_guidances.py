"""Read-only recap guidance adapter backed by a job settings snapshot."""

from notekeeper.application.errors import InvalidOperationError
from notekeeper.application.ports import RecapGuidances
from notekeeper.domain import CampaignId, ProcessingSettingsSnapshot


class SnapshotRecapGuidances(RecapGuidances):
    def __init__(self, snapshot: ProcessingSettingsSnapshot) -> None:
        self._snapshot = snapshot

    def get_chunk_recap_guidances(self, campaign_id: CampaignId) -> str:
        return self._snapshot.chunk_recap_prompt

    def get_combined_recap_guidances(self, campaign_id: CampaignId) -> str:
        return self._snapshot.combine_chunks_prompt

    def save_recap_guidances(
        self,
        campaign_id: CampaignId,
        *,
        chunk_recap_guidances: str,
        combined_recap_guidances: str,
    ) -> None:
        raise InvalidOperationError("processing settings snapshot is read-only")

    def reset_recap_guidances(self, campaign_id: CampaignId) -> None:
        raise InvalidOperationError("processing settings snapshot is read-only")


__all__ = ["SnapshotRecapGuidances"]
