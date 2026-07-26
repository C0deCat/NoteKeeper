"""Factory for streaming progress trackers."""

from notekeeper.application.ports import (
    ProgressEventPublisher,
    ProgressTracker,
)
from notekeeper.domain import ProcessingStage

from .progress_tracker import StreamingProgressTracker


class StreamingProgressTrackerFactory:
    def __init__(self, publisher: ProgressEventPublisher) -> None:
        self._publisher = publisher

    def create(
        self,
        operation_id: str,
        stages: tuple[ProcessingStage, ...],
    ) -> ProgressTracker:
        return StreamingProgressTracker(
            self._publisher,
            operation_id,
            stages,
        )


__all__ = ["StreamingProgressTrackerFactory"]
