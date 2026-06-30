"""Shared recap-generation orchestration."""

from notekeeper.application.ports import (
    IdGenerator,
    RecapGenerator,
    RecapRepository,
    Tokenizer,
)
from notekeeper.domain import Recap, RecapChunk, RecapId, Transcript

DEFAULT_RECAP_CHUNK_TOKEN_TARGET = 30_000


def generate_recap_for_transcript(
    transcript: Transcript,
    *,
    id_generator: IdGenerator,
    tokenizer: Tokenizer,
    recap_generator: RecapGenerator,
    recap_repository: RecapRepository,
    target_token_count: int = DEFAULT_RECAP_CHUNK_TOKEN_TARGET,
) -> Recap:
    chunks = tokenizer.split_transcript(
        transcript,
        target_token_count=target_token_count,
    )
    recap_chunks = tuple(
        RecapChunk(
            markdown=recap_generator.generate_chunk(chunk),
            time_range=chunk.time_range,
            source_segment_indexes=chunk.source_segment_indexes,
        )
        for chunk in chunks
    )
    recap = Recap(
        id=RecapId(id_generator.recap_id()),
        transcript_id=transcript.id,
        markdown=recap_generator.combine_chunks(recap_chunks),
        chunks=recap_chunks,
    )
    recap_repository.save(recap)
    return recap
