"""Participant update campaign service."""

from dataclasses import replace

from ..errors import CampaignValidationError
from ..models import Campaign, Participant
from .utils import replace_member


def update_participant(campaign: Campaign, participant: Participant) -> Campaign:
    if participant.campaign_id != campaign.id:
        raise CampaignValidationError("participant belongs to another campaign")

    participants = replace_member(
        campaign.participants,
        participant.id,
        participant,
        "participant",
    )
    return replace(campaign, participants=participants)
