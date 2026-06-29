"""Voice sample campaign service."""

from dataclasses import replace

from ..errors import CampaignValidationError
from ..models import Campaign, VoiceSample


def add_voice_sample(campaign: Campaign, voice_sample: VoiceSample) -> Campaign:
    if voice_sample.campaign_id != campaign.id:
        raise CampaignValidationError("voice sample belongs to another campaign")

    participant_ids = {participant.id for participant in campaign.participants}
    if voice_sample.participant_id not in participant_ids:
        raise CampaignValidationError("voice sample participant is not in the campaign")

    return replace(campaign, voice_samples=campaign.voice_samples + (voice_sample,))
