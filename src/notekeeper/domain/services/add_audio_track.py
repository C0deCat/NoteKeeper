"""Audio track campaign service."""

from dataclasses import replace

from ..errors import CampaignValidationError
from ..models import AudioTrack, Campaign


def add_audio_track(campaign: Campaign, audio_track: AudioTrack) -> Campaign:
    if audio_track.campaign_id != campaign.id:
        raise CampaignValidationError("audio track belongs to another campaign")

    return replace(campaign, audio_tracks=campaign.audio_tracks + (audio_track,))
