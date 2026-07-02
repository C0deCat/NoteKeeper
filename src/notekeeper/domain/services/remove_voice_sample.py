"""Voice sample removal campaign service."""

from dataclasses import replace

from ..errors import CampaignValidationError
from ..ids import VoiceSampleId
from ..models import Campaign


def remove_voice_sample(
    campaign: Campaign,
    voice_sample_id: VoiceSampleId,
) -> Campaign:
    if not any(sample.id == voice_sample_id for sample in campaign.voice_samples):
        raise CampaignValidationError("voice sample is not in the campaign")

    voice_samples = tuple(
        sample for sample in campaign.voice_samples if sample.id != voice_sample_id
    )
    return replace(campaign, voice_samples=voice_samples)
