"""List campaign voice samples use case."""

from notekeeper.application.commands import ListVoiceSamplesCommand
from notekeeper.application.ports import CampaignRepository
from notekeeper.application.results import ListVoiceSamplesResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId, ParticipantId


class ListVoiceSamples:
    def __init__(self, campaign_repository: CampaignRepository) -> None:
        self._campaign_repository = campaign_repository

    def execute(self, command: ListVoiceSamplesCommand) -> ListVoiceSamplesResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        samples = campaign.voice_samples
        if command.participant_id is not None:
            participant_id = ParticipantId(command.participant_id)
            samples = tuple(
                sample for sample in samples if sample.participant_id == participant_id
            )
        return ListVoiceSamplesResult(voice_samples=samples)
