"""Update campaign audio track use case."""

from dataclasses import replace

from notekeeper.application.commands import UpdateAudioTrackCommand
from notekeeper.application.ports import (
    AudioMetadataReader,
    AudioRecordingNormalizer,
    CampaignArtifactStorage,
    CampaignRepository,
)
from notekeeper.application.results import UpdateAudioTrackResult
from notekeeper.application.use_cases.campaigns.utils import find_audio_track
from notekeeper.application.use_cases.utils import (
    _require_campaign,
    delete_artifact_with_warning,
)
from notekeeper.domain import ArtifactRef, CampaignId, update_audio_track


class UpdateAudioTrack:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        metadata_reader: AudioMetadataReader,
        *,
        audio_normalizer: AudioRecordingNormalizer,
        artifact_storage: CampaignArtifactStorage,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._metadata_reader = metadata_reader
        self._audio_normalizer = audio_normalizer
        self._artifact_storage = artifact_storage

    def execute(self, command: UpdateAudioTrackCommand) -> UpdateAudioTrackResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        audio_track = find_audio_track(campaign.audio_tracks, command.audio_track_id)
        source_artifact = ArtifactRef(
            uri=command.artifact_uri,
            kind=command.artifact_kind,
        )
        normalized = None
        if (
            source_artifact.uri == audio_track.artifact.uri
            and source_artifact.kind == audio_track.artifact.kind
        ):
            artifact = audio_track.artifact
            metadata = audio_track.metadata
        else:
            source_metadata = self._metadata_reader.read(source_artifact)
            normalized = self._audio_normalizer.normalize_artifact(
                campaign_id=campaign.id,
                audio_track_id=audio_track.id,
                source_artifact=source_artifact,
                source_metadata=source_metadata,
            )
            artifact = normalized.audio_artifact
            metadata = normalized.metadata
        updated_audio_track = replace(
            audio_track,
            artifact=artifact,
            metadata=metadata,
            title=command.title,
        )
        updated_campaign = update_audio_track(campaign, updated_audio_track)
        self._campaign_repository.save(updated_campaign)
        cleanup_warnings: tuple[str, ...] = ()
        if normalized is not None:
            cleanup_targets = {source_artifact}
            if audio_track.artifact.uri != source_artifact.uri:
                cleanup_targets.add(audio_track.artifact)
            for cleanup_target in cleanup_targets:
                if cleanup_target.uri == artifact.uri:
                    continue
                cleanup_warnings += delete_artifact_with_warning(
                    self._artifact_storage,
                    cleanup_target,
                )
        return UpdateAudioTrackResult(
            campaign=updated_campaign,
            audio_track=updated_audio_track,
            normalized_count=int(normalized is not None),
            bytes_freed=normalized.bytes_freed if normalized is not None else 0,
            cleanup_warnings=cleanup_warnings,
        )
