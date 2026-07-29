"""Register campaign audio track use case."""

from notekeeper.application.commands import RegisterAudioTrackCommand
from notekeeper.application.ports import (
    AudioMetadataReader,
    AudioRecordingNormalizer,
    CampaignArtifactStorage,
    CampaignRepository,
    IdGenerator,
)
from notekeeper.application.results import RegisterAudioTrackResult
from notekeeper.application.use_cases.utils import (
    _require_campaign,
    delete_artifact_with_warning,
)
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
        *,
        audio_normalizer: AudioRecordingNormalizer,
        artifact_storage: CampaignArtifactStorage,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._metadata_reader = metadata_reader
        self._id_generator = id_generator
        self._audio_normalizer = audio_normalizer
        self._artifact_storage = artifact_storage

    def execute(self, command: RegisterAudioTrackCommand) -> RegisterAudioTrackResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        source_artifact = ArtifactRef(
            uri=command.artifact_uri,
            kind=command.artifact_kind,
        )
        audio_track_id = AudioTrackId(self._id_generator.audio_track_id())
        source_metadata = self._metadata_reader.read(source_artifact)
        normalized = self._audio_normalizer.normalize_artifact(
            campaign_id=campaign.id,
            audio_track_id=audio_track_id,
            source_artifact=source_artifact,
            source_metadata=source_metadata,
        )
        audio_track = AudioTrack(
            id=audio_track_id,
            campaign_id=campaign.id,
            artifact=normalized.audio_artifact,
            metadata=normalized.metadata,
            title=command.title,
        )
        updated_campaign = add_audio_track(campaign, audio_track)
        self._campaign_repository.save(updated_campaign)
        cleanup_warnings = ()
        if source_artifact.uri != normalized.audio_artifact.uri:
            cleanup_warnings = delete_artifact_with_warning(
                self._artifact_storage,
                source_artifact,
            )
        return RegisterAudioTrackResult(
            campaign=updated_campaign,
            audio_track=audio_track,
            normalized_count=1,
            bytes_freed=normalized.bytes_freed,
            cleanup_warnings=cleanup_warnings,
        )
