"""Update campaign audio track use case."""

from dataclasses import replace

from notekeeper.application.commands import UpdateAudioTrackCommand
from notekeeper.application.ports import AudioMetadataReader, CampaignRepository
from notekeeper.application.results import UpdateAudioTrackResult
from notekeeper.application.use_cases.campaigns.utils import find_audio_track
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import ArtifactRef, CampaignId, update_audio_track


class UpdateAudioTrack:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        metadata_reader: AudioMetadataReader,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._metadata_reader = metadata_reader

    def execute(self, command: UpdateAudioTrackCommand) -> UpdateAudioTrackResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        audio_track = find_audio_track(campaign.audio_tracks, command.audio_track_id)
        artifact = ArtifactRef(uri=command.artifact_uri, kind=command.artifact_kind)
        updated_audio_track = replace(
            audio_track,
            artifact=artifact,
            metadata=self._metadata_reader.read(artifact),
            title=command.title,
        )
        updated_campaign = update_audio_track(campaign, updated_audio_track)
        self._campaign_repository.save(updated_campaign)
        return UpdateAudioTrackResult(
            campaign=updated_campaign,
            audio_track=updated_audio_track,
        )
