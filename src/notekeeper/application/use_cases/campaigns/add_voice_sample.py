"""Add voice sample to campaign use case."""

from notekeeper.application.commands import AddVoiceSampleCommand
from notekeeper.application.ports import (
    AudioMetadataReader,
    CampaignRepository,
    IdGenerator,
)
from notekeeper.application.results import AddVoiceSampleResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import (
    ArtifactRef,
    CampaignId,
    ParticipantId,
    VoiceSample,
    VoiceSampleId,
    add_voice_sample,
)


class AddVoiceSample:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        metadata_reader: AudioMetadataReader,
        id_generator: IdGenerator,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._metadata_reader = metadata_reader
        self._id_generator = id_generator

    def execute(self, command: AddVoiceSampleCommand) -> AddVoiceSampleResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        artifact = ArtifactRef(uri=command.artifact_uri, kind=command.artifact_kind)
        voice_sample = VoiceSample(
            id=VoiceSampleId(self._id_generator.voice_sample_id()),
            campaign_id=campaign.id,
            participant_id=ParticipantId(command.participant_id),
            artifact=artifact,
            metadata=self._metadata_reader.read(artifact),
            recorded_at=command.recorded_at,
        )
        updated_campaign = add_voice_sample(campaign, voice_sample)
        self._campaign_repository.save(updated_campaign)
        return AddVoiceSampleResult(
            campaign=updated_campaign,
            voice_sample=voice_sample,
        )
