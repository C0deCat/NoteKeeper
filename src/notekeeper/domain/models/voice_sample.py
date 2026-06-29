"""Voice sample entity."""

from dataclasses import dataclass
from datetime import datetime

from ..ids import CampaignId, ParticipantId, VoiceSampleId
from ..value_objects import ArtifactRef, AudioMetadata


@dataclass(frozen=True, slots=True)
class VoiceSample:
    id: VoiceSampleId
    campaign_id: CampaignId
    participant_id: ParticipantId
    artifact: ArtifactRef
    metadata: AudioMetadata
    recorded_at: datetime | None = None
