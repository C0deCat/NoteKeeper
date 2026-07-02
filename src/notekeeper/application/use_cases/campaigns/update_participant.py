"""Update campaign participant use case."""

from dataclasses import replace

from notekeeper.application.commands import UpdateParticipantCommand
from notekeeper.application.ports import CampaignRepository
from notekeeper.application.results import UpdateParticipantResult
from notekeeper.application.use_cases.campaigns.utils import find_participant
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId, update_participant


class UpdateParticipant:
    def __init__(self, campaign_repository: CampaignRepository) -> None:
        self._campaign_repository = campaign_repository

    def execute(self, command: UpdateParticipantCommand) -> UpdateParticipantResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        participant = find_participant(campaign.participants, command.participant_id)
        updated_participant = replace(participant, display_name=command.display_name)
        updated_campaign = update_participant(campaign, updated_participant)
        self._campaign_repository.save(updated_campaign)
        return UpdateParticipantResult(
            campaign=updated_campaign,
            participant=updated_participant,
        )
