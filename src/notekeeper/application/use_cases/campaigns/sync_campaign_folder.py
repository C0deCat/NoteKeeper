"""Synchronize a campaign folder snapshot into application state."""

from dataclasses import replace

from notekeeper.application.commands import SyncCampaignFolderCommand
from notekeeper.application.ports import (
    AudioMetadataReader,
    CampaignFolderScanner,
    CampaignRepository,
    IdGenerator,
    JobRepository,
)
from notekeeper.application.results import SyncCampaignFolderResult
from notekeeper.application.use_cases.campaigns.utils import delete_pending_jobs
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import (
    AudioTrack,
    AudioTrackId,
    Campaign,
    CampaignId,
    Participant,
    ParticipantId,
    VoiceSample,
    VoiceSampleId,
    add_audio_track,
    add_participant,
    add_voice_sample,
    remove_audio_track,
    remove_voice_sample,
    update_audio_track,
    update_voice_sample,
)


class SyncCampaignFolder:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        job_repository: JobRepository,
        folder_scanner: CampaignFolderScanner,
        metadata_reader: AudioMetadataReader,
        id_generator: IdGenerator,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._job_repository = job_repository
        self._folder_scanner = folder_scanner
        self._metadata_reader = metadata_reader
        self._id_generator = id_generator

    def execute(
        self,
        command: SyncCampaignFolderCommand,
    ) -> SyncCampaignFolderResult:
        campaign_id = CampaignId(command.campaign_id)
        campaign = _require_campaign(self._campaign_repository, campaign_id)
        snapshot = self._folder_scanner.scan(campaign_id)

        participants_created = 0
        samples_added = 0
        samples_updated = 0
        samples_deleted = 0
        tracks_added = 0
        tracks_updated = 0
        tracks_deleted = 0
        pending_jobs_deleted = 0

        participants_by_name = {
            participant.display_name.casefold(): participant
            for participant in campaign.participants
        }

        for scanned_sample in snapshot.voice_samples:
            name_key = scanned_sample.player_name.casefold()
            if name_key in participants_by_name:
                continue

            participant = Participant(
                id=ParticipantId(self._id_generator.participant_id()),
                campaign_id=campaign.id,
                display_name=scanned_sample.player_name,
            )
            campaign = add_participant(campaign, participant)
            participants_by_name[name_key] = participant
            participants_created += 1

        sample_uris = {sample.artifact.uri for sample in snapshot.voice_samples}
        samples_by_uri = {sample.artifact.uri: sample for sample in campaign.voice_samples}
        for scanned_sample in snapshot.voice_samples:
            participant = participants_by_name[scanned_sample.player_name.casefold()]
            metadata = self._metadata_reader.read(scanned_sample.artifact)
            existing = samples_by_uri.get(scanned_sample.artifact.uri)
            if existing is None:
                voice_sample = VoiceSample(
                    id=VoiceSampleId(self._id_generator.voice_sample_id()),
                    campaign_id=campaign.id,
                    participant_id=participant.id,
                    artifact=scanned_sample.artifact,
                    metadata=metadata,
                )
                campaign = add_voice_sample(campaign, voice_sample)
                samples_added += 1
                continue

            updated_sample = replace(
                existing,
                participant_id=participant.id,
                artifact=scanned_sample.artifact,
                metadata=metadata,
            )
            if updated_sample != existing:
                campaign = update_voice_sample(campaign, updated_sample)
                samples_updated += 1

        for sample in tuple(campaign.voice_samples):
            if sample.artifact.uri not in sample_uris:
                campaign = remove_voice_sample(campaign, sample.id)
                samples_deleted += 1

        track_uris = {track.artifact.uri for track in snapshot.audio_tracks}
        tracks_by_uri = {track.artifact.uri: track for track in campaign.audio_tracks}
        for scanned_track in snapshot.audio_tracks:
            metadata = self._metadata_reader.read(scanned_track.artifact)
            existing = tracks_by_uri.get(scanned_track.artifact.uri)
            if existing is None:
                audio_track = AudioTrack(
                    id=AudioTrackId(self._id_generator.audio_track_id()),
                    campaign_id=campaign.id,
                    artifact=scanned_track.artifact,
                    metadata=metadata,
                    title=scanned_track.title,
                )
                campaign = add_audio_track(campaign, audio_track)
                tracks_added += 1
                continue

            updated_track = replace(
                existing,
                artifact=scanned_track.artifact,
                metadata=metadata,
                title=scanned_track.title,
            )
            if updated_track != existing:
                campaign = update_audio_track(campaign, updated_track)
                tracks_updated += 1

        for audio_track in tuple(campaign.audio_tracks):
            if audio_track.artifact.uri not in track_uris:
                pending_jobs_deleted += delete_pending_jobs(
                    self._job_repository,
                    audio_track.id,
                )
                campaign = remove_audio_track(campaign, audio_track.id)
                tracks_deleted += 1

        self._campaign_repository.save(campaign)
        return SyncCampaignFolderResult(
            campaign=campaign,
            participants_created=participants_created,
            voice_samples_added=samples_added,
            voice_samples_updated=samples_updated,
            voice_samples_deleted=samples_deleted,
            audio_tracks_added=tracks_added,
            audio_tracks_updated=tracks_updated,
            audio_tracks_deleted=tracks_deleted,
            pending_jobs_deleted=pending_jobs_deleted,
        )
