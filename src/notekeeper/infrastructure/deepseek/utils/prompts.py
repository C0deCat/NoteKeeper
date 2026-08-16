"""Prompt rendering for DeepSeek recap requests."""

from notekeeper.application.results import TranscriptChunk
from notekeeper.domain import RecapChunk, TimeRange


def chunk_user_message(chunk: TranscriptChunk) -> str:
    parts = ["Transcript chunk metadata:", _chunk_metadata(chunk), ""]
    parts.extend(("Transcript chunk:", chunk.text))
    return "\n".join(parts).strip()


def combined_user_message(chunks: tuple[RecapChunk, ...]) -> str:
    if not chunks:
        return "Partial recaps: none"

    parts = ["Partial recaps:"]
    for index, chunk in enumerate(chunks, start=1):
        parts.extend(
            (
                "",
                f"## Partial recap {index}",
                _recap_chunk_metadata(chunk),
                "",
                chunk.markdown,
            )
        )
    return "\n".join(parts).strip()


def _chunk_metadata(chunk: TranscriptChunk) -> str:
    return _source_metadata(chunk.time_range, chunk.source_segment_indexes)


def _recap_chunk_metadata(chunk: RecapChunk) -> str:
    return _source_metadata(chunk.time_range, chunk.source_segment_indexes)


def _source_metadata(
    time_range: TimeRange | None,
    source_segment_indexes: tuple[int, ...],
) -> str:
    return "\n".join(
        (
            f"time_range: {_format_time_range(time_range)}",
            f"source_segment_indexes: {_format_indexes(source_segment_indexes)}",
        )
    )


def _format_time_range(time_range: TimeRange | None) -> str:
    if time_range is None:
        return "unknown"
    return (
        f"{_format_seconds(time_range.start_seconds)} - "
        f"{_format_seconds(time_range.end_seconds)}"
    )


def _format_indexes(indexes: tuple[int, ...]) -> str:
    return ", ".join(str(index) for index in indexes) if indexes else "none"


def _format_seconds(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"


__all__ = ["chunk_user_message", "combined_user_message"]
