"""Speaker label value object."""

from __future__ import annotations

from dataclasses import dataclass

from ..enums import SpeakerLabelKind
from ..validation import non_empty_str


@dataclass(frozen=True, slots=True)
class SpeakerLabel:
    value: str
    kind: SpeakerLabelKind

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", non_empty_str(self.value, "value"))

    @classmethod
    def anonymous(cls, value: str) -> SpeakerLabel:
        return cls(value=value, kind=SpeakerLabelKind.ANONYMOUS)

    @classmethod
    def named(cls, value: str) -> SpeakerLabel:
        return cls(value=value, kind=SpeakerLabelKind.NAMED)
