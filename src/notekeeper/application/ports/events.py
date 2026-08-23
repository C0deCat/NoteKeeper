"""Application event and progress ports."""

from collections.abc import Callable
from typing import Protocol

from notekeeper.application.results import DashboardChangedEvent, ProgressEvent
from notekeeper.domain import ProcessingStage

ProgressEventListener = Callable[[ProgressEvent], None]
DashboardEventListener = Callable[[DashboardChangedEvent], None]
Unsubscribe = Callable[[], None]


class DashboardEventPublisher(Protocol):
    def publish(self, event: DashboardChangedEvent) -> None: ...


class DashboardEventStream(Protocol):
    def subscribe(self, listener: DashboardEventListener) -> Unsubscribe: ...


class DashboardEventHub(DashboardEventPublisher, DashboardEventStream, Protocol):
    pass


class ProgressEventPublisher(Protocol):
    def publish(self, event: ProgressEvent) -> None: ...


class ProgressEventStream(Protocol):
    def subscribe(
        self,
        operation_id: str,
        listener: ProgressEventListener,
        *,
        replay_latest: bool = True,
    ) -> Unsubscribe: ...

    def latest(self, operation_id: str) -> ProgressEvent | None: ...


class ProgressEventHub(ProgressEventPublisher, ProgressEventStream, Protocol):
    pass


class ProgressEventSnapshotStore(Protocol):
    def get(self, operation_id: str) -> ProgressEvent | None: ...

    def save(self, event: ProgressEvent) -> None: ...

    def delete(self, operation_id: str) -> None: ...


class ProgressTracker(Protocol):
    def start_stage(
        self,
        stage: ProcessingStage,
        *,
        timing_available: bool,
    ) -> None: ...

    def update_fraction(self, fraction: float) -> None: ...

    def complete_stage(self) -> None: ...

    def complete(self) -> None: ...

    def pause(self) -> None: ...

    def fail(self) -> None: ...

    def cancel(self) -> None: ...

    def close(self) -> None: ...


class ProgressTrackerFactory(Protocol):
    def create(
        self,
        operation_id: str,
        stages: tuple[ProcessingStage, ...],
    ) -> ProgressTracker: ...
