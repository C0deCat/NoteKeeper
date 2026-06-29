"""Speaker mapping value object."""

from dataclasses import dataclass

from ..enums import SpeakerLabelKind, SpeakerMappingSource, SpeakerMappingStatus
from ..errors import SpeakerMappingError
from ..ids import ParticipantId
from ..validation import finite_float
from .speaker_label import SpeakerLabel


@dataclass(frozen=True, slots=True)
class SpeakerMapping:
    anonymous_label: SpeakerLabel
    named_label: SpeakerLabel | None
    participant_id: ParticipantId | None
    confidence: float | None
    source: SpeakerMappingSource
    status: SpeakerMappingStatus

    def __post_init__(self) -> None:
        if self.anonymous_label.kind is not SpeakerLabelKind.ANONYMOUS:
            raise SpeakerMappingError("anonymous_label must be anonymous")

        if (
            self.named_label is not None
            and self.named_label.kind is not SpeakerLabelKind.NAMED
        ):
            raise SpeakerMappingError("named_label must be named")

        if self.confidence is not None:
            confidence = finite_float(self.confidence, "confidence")
            if confidence < 0 or confidence > 1:
                raise SpeakerMappingError("confidence must be between 0 and 1")
            object.__setattr__(self, "confidence", confidence)

        if self.status is SpeakerMappingStatus.CONFIRMED:
            if self.named_label is None:
                raise SpeakerMappingError("confirmed mapping must have a named_label")
            if self.participant_id is None:
                raise SpeakerMappingError("confirmed mapping must have a participant_id")
