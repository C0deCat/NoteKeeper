"""Add voice sample to campaign use case."""

from notekeeper.application.commands import AddVoiceSampleCommand
from notekeeper.application.ports import (
    AudioMetadataReader,
    CampaignArtifactStorage,
    CampaignRepository,
    IdGenerator,
    SourceAudioMetadataReader,
)
from notekeeper.application.results import AddVoiceSampleResult
from notekeeper.application.use_cases.utils import (
    _require_campaign,
    resolve_audio_source,
)
from notekeeper.domain import (
    ArtifactRef,
    CampaignId,
    ParticipantId,
    VoiceSample,
    VoiceSampleId,
    add_voice_sample,
)

from .utils import find_participant


class AddVoiceSample:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        metadata_reader: AudioMetadataReader,
        source_metadata_reader: SourceAudioMetadataReader,
        artifact_storage: CampaignArtifactStorage,
        id_generator: IdGenerator,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._metadata_reader = metadata_reader
        self._source_metadata_reader = source_metadata_reader
        self._artifact_storage = artifact_storage
        self._id_generator = id_generator

    def execute(self, command: AddVoiceSampleCommand) -> AddVoiceSampleResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        artifact_uri, source_path = resolve_audio_source(
            command.artifact_uri,
            command.source_path,
        )
        if source_path is not None:
            participant = find_participant(
                campaign.participants,
                command.participant_id,
            )
            metadata = self._source_metadata_reader.read(source_path)
            artifact = self._artifact_storage.import_file(
                campaign_id=campaign.id,
                folder="players",
                source_path=source_path,
                player_name=participant.display_name,
            )
        else:
            artifact = ArtifactRef(
                uri=artifact_uri or "",
                kind=command.artifact_kind,
            )
            metadata = self._metadata_reader.read(artifact)

        voice_sample = VoiceSample(
            id=VoiceSampleId(self._id_generator.voice_sample_id()),
            campaign_id=campaign.id,
            participant_id=ParticipantId(command.participant_id),
            artifact=artifact,
            metadata=metadata,
            recorded_at=command.recorded_at,
        )
        updated_campaign = add_voice_sample(campaign, voice_sample)
        self._campaign_repository.save(updated_campaign)
        return AddVoiceSampleResult(
            campaign=updated_campaign,
            voice_sample=voice_sample,
        )
