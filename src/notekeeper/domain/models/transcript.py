"""Transcript entities."""

from dataclasses import dataclass

from ..errors import DomainValidationError
from ..ids import AudioTrackId, CampaignId, TranscriptId
from ..validation import as_tuple, non_empty_str
from ..value_objects import SpeakerLabel, TimeRange


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    index: int
    time_range: TimeRange
    speaker_label: SpeakerLabel
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.index, int) or self.index < 0:
            raise DomainValidationError("index must be a non-negative integer")

        object.__setattr__(self, "text", non_empty_str(self.text, "text"))


@dataclass(frozen=True, slots=True)
class Transcript:
    id: TranscriptId
    campaign_id: CampaignId
    audio_track_id: AudioTrackId
    segments: tuple[TranscriptSegment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "segments", as_tuple(self.segments, "segments"))
