"""Ports used to tokenize transcripts and generate recaps."""

from typing import Protocol

from notekeeper.application.results import RecapGenerationContext, TranscriptChunk
from notekeeper.domain import CampaignId, RecapChunk


class RecapGuidances(Protocol):
    def get_chunk_recap_guidances(self, campaign_id: CampaignId) -> str: ...

    def get_combined_recap_guidances(self, campaign_id: CampaignId) -> str: ...

    def save_recap_guidances(
        self,
        campaign_id: CampaignId,
        *,
        chunk_recap_guidances: str,
        combined_recap_guidances: str,
    ) -> None: ...


class RecapGenerator(Protocol):
    def generate_chunk(
        self,
        chunk: TranscriptChunk,
        *,
        guidance: str,
        context: RecapGenerationContext,
    ) -> str: ...

    def combine_chunks(
        self,
        chunks: tuple[RecapChunk, ...],
        *,
        guidance: str,
        context: RecapGenerationContext,
    ) -> str: ...
