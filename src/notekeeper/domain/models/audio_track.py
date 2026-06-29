"""Audio track entity."""

from dataclasses import dataclass

from ..ids import AudioTrackId, CampaignId
from ..validation import optional_non_empty_str
from ..value_objects import ArtifactRef, AudioMetadata


@dataclass(frozen=True, slots=True)
class AudioTrack:
    id: AudioTrackId
    campaign_id: CampaignId
    artifact: ArtifactRef
    metadata: AudioMetadata
    title: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", optional_non_empty_str(self.title, "title"))
