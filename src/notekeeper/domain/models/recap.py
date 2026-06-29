"""Recap entities."""

from dataclasses import dataclass

from ..errors import DomainValidationError
from ..ids import RecapId, TranscriptId
from ..validation import as_tuple, non_empty_str
from ..value_objects import TimeRange


@dataclass(frozen=True, slots=True)
class RecapChunk:
    markdown: str
    time_range: TimeRange | None = None
    source_segment_indexes: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "markdown", non_empty_str(self.markdown, "markdown"))
        object.__setattr__(
            self,
            "source_segment_indexes",
            as_tuple(self.source_segment_indexes, "source_segment_indexes"),
        )

        for index in self.source_segment_indexes:
            if not isinstance(index, int) or index < 0:
                raise DomainValidationError(
                    "source_segment_indexes must contain non-negative integers"
                )


@dataclass(frozen=True, slots=True)
class Recap:
    id: RecapId
    transcript_id: TranscriptId
    markdown: str
    chunks: tuple[RecapChunk, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "markdown", non_empty_str(self.markdown, "markdown"))
        object.__setattr__(self, "chunks", as_tuple(self.chunks, "chunks"))
