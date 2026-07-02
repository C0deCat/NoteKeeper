"""Participant removal campaign service."""

from dataclasses import replace

from ..errors import CampaignValidationError
from ..ids import ParticipantId
from ..models import Campaign


def remove_participant(campaign: Campaign, participant_id: ParticipantId) -> Campaign:
    if not any(participant.id == participant_id for participant in campaign.participants):
        raise CampaignValidationError("participant is not in the campaign")

    participants = tuple(
        participant
        for participant in campaign.participants
        if participant.id != participant_id
    )
    voice_samples = tuple(
        sample for sample in campaign.voice_samples if sample.participant_id != participant_id
    )
    return replace(campaign, participants=participants, voice_samples=voice_samples)
