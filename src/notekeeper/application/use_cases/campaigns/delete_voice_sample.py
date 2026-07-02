"""Delete campaign voice sample use case."""

from notekeeper.application.commands import DeleteVoiceSampleCommand
from notekeeper.application.ports import CampaignRepository
from notekeeper.application.results import DeleteVoiceSampleResult
from notekeeper.application.use_cases.campaigns.utils import find_voice_sample
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId, VoiceSampleId, remove_voice_sample


class DeleteVoiceSample:
    def __init__(self, campaign_repository: CampaignRepository) -> None:
        self._campaign_repository = campaign_repository

    def execute(self, command: DeleteVoiceSampleCommand) -> DeleteVoiceSampleResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        voice_sample_id = VoiceSampleId(command.voice_sample_id)
        find_voice_sample(campaign.voice_samples, command.voice_sample_id)
        updated_campaign = remove_voice_sample(campaign, voice_sample_id)
        self._campaign_repository.save(updated_campaign)
        return DeleteVoiceSampleResult(
            campaign=updated_campaign,
            voice_sample_id=command.voice_sample_id,
        )
