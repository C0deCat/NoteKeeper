"""Campaign readiness service."""

from ..errors import CampaignValidationError
from ..models import Campaign


def ensure_campaign_ready_for_processing(campaign: Campaign) -> None:
    if not campaign.participants:
        raise CampaignValidationError("campaign must have at least one participant")

    sample_participant_ids = {
        voice_sample.participant_id for voice_sample in campaign.voice_samples
    }

    for participant in campaign.participants:
        if participant.id not in sample_participant_ids:
            raise CampaignValidationError(
                f"participant {participant.display_name} has no voice sample"
            )
