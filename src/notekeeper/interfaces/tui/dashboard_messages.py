"""Dashboard selection models and internal Textual messages."""

from dataclasses import dataclass

from textual.message import Message

from notekeeper.application import ConsoleLogEvent, DashboardChangedEvent, ProgressEvent
from notekeeper.domain import AudioTrack, Participant, ProcessingJob


@dataclass(frozen=True, slots=True)
class DashboardWarning:
    """Selectable dashboard representation of a warning or job error row."""

    key: str
    job_id: str
    kind: str
    message: str


SelectedObject = ProcessingJob | AudioTrack | Participant | DashboardWarning


class DashboardInvalidated(Message):
    def __init__(self, event: DashboardChangedEvent) -> None:
        super().__init__()
        self.event = event


class ProgressChanged(Message):
    def __init__(self, event: ProgressEvent) -> None:
        super().__init__()
        self.event = event


class ConsoleLogChanged(Message):
    def __init__(self, event: ConsoleLogEvent) -> None:
        super().__init__()
        self.event = event


__all__ = [
    "DashboardInvalidated",
    "DashboardWarning",
    "ConsoleLogChanged",
    "ProgressChanged",
    "SelectedObject",
]
