"""Delete campaign participant use case."""

from notekeeper.application.commands import DeleteParticipantCommand
from notekeeper.application.ports import CampaignRepository
from notekeeper.application.results import DeleteParticipantResult
from notekeeper.application.use_cases.campaigns.utils import find_participant
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId, ParticipantId, remove_participant


class DeleteParticipant:
    def __init__(self, campaign_repository: CampaignRepository) -> None:
        self._campaign_repository = campaign_repository

    def execute(self, command: DeleteParticipantCommand) -> DeleteParticipantResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        participant_id = ParticipantId(command.participant_id)
        find_participant(campaign.participants, command.participant_id)
        updated_campaign = remove_participant(campaign, participant_id)
        self._campaign_repository.save(updated_campaign)
        return DeleteParticipantResult(
            campaign=updated_campaign,
            participant_id=command.participant_id,
        )
