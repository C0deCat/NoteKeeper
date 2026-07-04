"""Shared recap-generation orchestration."""

from notekeeper.application.ports import (
    IdGenerator,
    RecapGenerator,
    RecapRepository,
    Tokenizer,
)
from notekeeper.application.results import RecapGenerationContext
from notekeeper.domain import ProcessingJobId, Recap, RecapChunk, RecapId, Transcript

DEFAULT_RECAP_CHUNK_TOKEN_TARGET = 30_000


def generate_recap_for_transcript(
    transcript: Transcript,
    *,
    id_generator: IdGenerator,
    tokenizer: Tokenizer,
    recap_generator: RecapGenerator,
    recap_repository: RecapRepository,
    target_token_count: int = DEFAULT_RECAP_CHUNK_TOKEN_TARGET,
    job_id: ProcessingJobId | None = None,
) -> Recap:
    recap_id = RecapId(id_generator.recap_id())
    chunks = tokenizer.split_transcript(
        transcript,
        target_token_count=target_token_count,
    )
    recap_chunks = tuple(
        RecapChunk(
            markdown=recap_generator.generate_chunk(
                chunk,
                context=RecapGenerationContext(
                    campaign_id=transcript.campaign_id,
                    transcript_id=transcript.id,
                    recap_id=recap_id,
                    job_id=job_id,
                    chunk_index=chunk_index,
                ),
            ),
            time_range=chunk.time_range,
            source_segment_indexes=chunk.source_segment_indexes,
        )
        for chunk_index, chunk in enumerate(chunks)
    )
    recap = Recap(
        id=recap_id,
        transcript_id=transcript.id,
        markdown=recap_generator.combine_chunks(
            recap_chunks,
            context=RecapGenerationContext(
                campaign_id=transcript.campaign_id,
                transcript_id=transcript.id,
                recap_id=recap_id,
                job_id=job_id,
            ),
        ),
        chunks=recap_chunks,
    )
    recap_repository.save(recap)
    return recap
