"""Participant campaign service."""

from dataclasses import replace

from ..errors import CampaignValidationError
from ..models import Campaign, Participant


def add_participant(campaign: Campaign, participant: Participant) -> Campaign:
    if participant.campaign_id != campaign.id:
        raise CampaignValidationError("participant belongs to another campaign")

    return replace(campaign, participants=campaign.participants + (participant,))
