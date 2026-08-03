"""Shared recap-generation orchestration."""

from collections.abc import Callable

from notekeeper.application.ports import (
    IdGenerator,
    RecapGuidances,
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
    recap_guidances: RecapGuidances,
    recap_generator: RecapGenerator,
    recap_repository: RecapRepository,
    target_token_count: int = DEFAULT_RECAP_CHUNK_TOKEN_TARGET,
    job_id: ProcessingJobId | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> Recap:
    chunk_guidance = recap_guidances.get_chunk_recap_guidances(
        transcript.campaign_id,
    )
    combined_guidance = recap_guidances.get_combined_recap_guidances(
        transcript.campaign_id,
    )
    recap_id = RecapId(id_generator.recap_id())
    chunks = tokenizer.split_transcript(
        transcript,
        target_token_count=target_token_count,
    )
    request_count = len(chunks) + 1
    recap_chunks = []
    for chunk_index, chunk in enumerate(chunks):
        recap_chunks.append(
            RecapChunk(
                markdown=recap_generator.generate_chunk(
                    chunk,
                    guidance=chunk_guidance,
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
            ),
        )
        if progress_callback is not None:
            progress_callback((chunk_index + 1) / request_count)
    recap_chunks_tuple = tuple(recap_chunks)
    recap = Recap(
        id=recap_id,
        transcript_id=transcript.id,
        markdown=recap_generator.combine_chunks(
            recap_chunks_tuple,
            guidance=combined_guidance,
            context=RecapGenerationContext(
                campaign_id=transcript.campaign_id,
                transcript_id=transcript.id,
                recap_id=recap_id,
                job_id=job_id,
            ),
        ),
        chunks=recap_chunks_tuple,
    )
    if progress_callback is not None:
        progress_callback(1.0)
    recap_repository.save(recap)
    return recap
