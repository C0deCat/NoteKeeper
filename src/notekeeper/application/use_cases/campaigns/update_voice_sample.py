"""Update campaign voice sample use case."""

from dataclasses import replace

from notekeeper.application.commands import UpdateVoiceSampleCommand
from notekeeper.application.ports import AudioMetadataReader, CampaignRepository
from notekeeper.application.results import UpdateVoiceSampleResult
from notekeeper.application.use_cases.campaigns.utils import find_voice_sample
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import ArtifactRef, CampaignId, update_voice_sample


class UpdateVoiceSample:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        metadata_reader: AudioMetadataReader,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._metadata_reader = metadata_reader

    def execute(self, command: UpdateVoiceSampleCommand) -> UpdateVoiceSampleResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        voice_sample = find_voice_sample(
            campaign.voice_samples,
            command.voice_sample_id,
        )
        artifact = ArtifactRef(uri=command.artifact_uri, kind=command.artifact_kind)
        updated_voice_sample = replace(
            voice_sample,
            artifact=artifact,
            metadata=self._metadata_reader.read(artifact),
            recorded_at=command.recorded_at,
        )
        updated_campaign = update_voice_sample(campaign, updated_voice_sample)
        self._campaign_repository.save(updated_campaign)
        return UpdateVoiceSampleResult(
            campaign=updated_campaign,
            voice_sample=updated_voice_sample,
        )
