"""Participant entity."""

from dataclasses import dataclass

from ..ids import CampaignId, ParticipantId
from ..validation import non_empty_str


@dataclass(frozen=True, slots=True)
class Participant:
    id: ParticipantId
    campaign_id: CampaignId
    display_name: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "display_name",
            non_empty_str(self.display_name, "display_name"),
        )
