"""Audio track removal campaign service."""

from dataclasses import replace

from ..errors import CampaignValidationError
from ..ids import AudioTrackId
from ..models import Campaign


def remove_audio_track(campaign: Campaign, audio_track_id: AudioTrackId) -> Campaign:
    if not any(track.id == audio_track_id for track in campaign.audio_tracks):
        raise CampaignValidationError("audio track is not in the campaign")

    audio_tracks = tuple(
        track for track in campaign.audio_tracks if track.id != audio_track_id
    )
    return replace(campaign, audio_tracks=audio_tracks)
