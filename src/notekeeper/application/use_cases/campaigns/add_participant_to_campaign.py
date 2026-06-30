"""Add participant to campaign use case."""

from notekeeper.application.commands import AddParticipantToCampaignCommand
from notekeeper.application.ports import CampaignRepository, IdGenerator
from notekeeper.application.results import AddParticipantToCampaignResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import (
    CampaignId,
    Participant,
    ParticipantId,
    add_participant,
)


class AddParticipantToCampaign:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        id_generator: IdGenerator,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._id_generator = id_generator

    def execute(
        self,
        command: AddParticipantToCampaignCommand,
    ) -> AddParticipantToCampaignResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        participant = Participant(
            id=ParticipantId(self._id_generator.participant_id()),
            campaign_id=campaign.id,
            display_name=command.display_name,
        )
        updated_campaign = add_participant(campaign, participant)
        self._campaign_repository.save(updated_campaign)
        return AddParticipantToCampaignResult(
            campaign=updated_campaign,
            participant=participant,
        )
