"""Register campaign audio track use case."""

from notekeeper.application.commands import RegisterAudioTrackCommand
from notekeeper.application.ports import (
    AudioMetadataReader,
    CampaignRepository,
    IdGenerator,
)
from notekeeper.application.results import RegisterAudioTrackResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import (
    ArtifactRef,
    AudioTrack,
    AudioTrackId,
    CampaignId,
    add_audio_track,
)


class RegisterAudioTrack:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        metadata_reader: AudioMetadataReader,
        id_generator: IdGenerator,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._metadata_reader = metadata_reader
        self._id_generator = id_generator

    def execute(self, command: RegisterAudioTrackCommand) -> RegisterAudioTrackResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        artifact = ArtifactRef(uri=command.artifact_uri, kind=command.artifact_kind)
        audio_track = AudioTrack(
            id=AudioTrackId(self._id_generator.audio_track_id()),
            campaign_id=campaign.id,
            artifact=artifact,
            metadata=self._metadata_reader.read(artifact),
            title=command.title,
        )
        updated_campaign = add_audio_track(campaign, audio_track)
        self._campaign_repository.save(updated_campaign)
        return RegisterAudioTrackResult(
            campaign=updated_campaign,
            audio_track=audio_track,
        )
