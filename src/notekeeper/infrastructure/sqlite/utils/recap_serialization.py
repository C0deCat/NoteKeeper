"""Recap payload serialization."""

from typing import Any

from notekeeper.domain import Recap, RecapChunk, RecapId, TranscriptId

from .common_serialization import time_range_from_dict, time_range_to_dict


def recap_to_payload(recap: Recap) -> dict[str, Any]:
    return {
        "markdown": recap.markdown,
        "chunks": [
            {
                "markdown": chunk.markdown,
                "time_range": (
                    time_range_to_dict(chunk.time_range)
                    if chunk.time_range is not None
                    else None
                ),
                "source_segment_indexes": list(chunk.source_segment_indexes),
            }
            for chunk in recap.chunks
        ],
    }


def recap_from_payload(
    *,
    recap_id: str,
    transcript_id: str,
    payload: dict[str, Any],
) -> Recap:
    return Recap(
        id=RecapId(recap_id),
        transcript_id=TranscriptId(transcript_id),
        markdown=payload["markdown"],
        chunks=tuple(
            RecapChunk(
                markdown=chunk["markdown"],
                time_range=(
                    time_range_from_dict(chunk["time_range"])
                    if chunk.get("time_range") is not None
                    else None
                ),
                source_segment_indexes=tuple(chunk.get("source_segment_indexes", ())),
            )
            for chunk in payload.get("chunks", ())
        ),
    )


__all__ = ["recap_from_payload", "recap_to_payload"]
