"""Pipeline warning value object."""

from dataclasses import dataclass

from ..enums import PipelineWarningKind
from ..ids import ParticipantId
from ..validation import non_empty_str
from .speaker_label import SpeakerLabel
from .time_range import TimeRange


@dataclass(frozen=True, slots=True)
class PipelineWarning:
    kind: PipelineWarningKind
    message: str
    time_range: TimeRange | None = None
    speaker_label: SpeakerLabel | None = None
    participant_id: ParticipantId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "message", non_empty_str(self.message, "message"))
