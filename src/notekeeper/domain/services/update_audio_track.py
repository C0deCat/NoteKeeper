"""Audio track update campaign service."""

from dataclasses import replace

from ..errors import CampaignValidationError
from ..models import AudioTrack, Campaign
from .utils import replace_member


def update_audio_track(campaign: Campaign, audio_track: AudioTrack) -> Campaign:
    if audio_track.campaign_id != campaign.id:
        raise CampaignValidationError("audio track belongs to another campaign")

    audio_tracks = replace_member(
        campaign.audio_tracks,
        audio_track.id,
        audio_track,
        "audio track",
    )
    return replace(campaign, audio_tracks=audio_tracks)
