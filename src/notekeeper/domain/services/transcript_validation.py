"""Transcript validation service."""

from ..errors import TranscriptValidationError
from ..models import Transcript


def validate_transcript(transcript: Transcript) -> None:
    previous_end: float | None = None
    previous_index: int | None = None

    for segment in transcript.segments:
        if previous_index is not None and segment.index <= previous_index:
            raise TranscriptValidationError("transcript segment indexes must increase")

        if previous_end is not None and segment.time_range.start_seconds < previous_end:
            raise TranscriptValidationError("transcript segments must not overlap")

        previous_end = segment.time_range.end_seconds
        previous_index = segment.index
