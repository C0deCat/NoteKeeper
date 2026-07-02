"""Voice sample update campaign service."""

from dataclasses import replace

from ..errors import CampaignValidationError
from ..models import Campaign, VoiceSample
from .utils import replace_member


def update_voice_sample(campaign: Campaign, voice_sample: VoiceSample) -> Campaign:
    if voice_sample.campaign_id != campaign.id:
        raise CampaignValidationError("voice sample belongs to another campaign")

    voice_samples = replace_member(
        campaign.voice_samples,
        voice_sample.id,
        voice_sample,
        "voice sample",
    )
    return replace(campaign, voice_samples=voice_samples)
