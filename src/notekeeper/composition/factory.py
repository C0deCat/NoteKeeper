"""Infrastructure composition factory."""

from __future__ import annotations

from dataclasses import dataclass

from notekeeper.infrastructure.filesystem import (
    LocalAudioMetadataReader,
    LocalCampaignArtifactStorage,
    LocalCampaignFolderScanner,
)
from notekeeper.infrastructure.runtime import SystemClock, UuidGenerator
from notekeeper.infrastructure.sqlite import (
    SQLiteAudioTrackRepository,
    SQLiteCampaignRepository,
    SQLiteDatabase,
    SQLiteJobRepository,
    SQLiteParticipantRepository,
    SQLiteRecapRepository,
    SQLiteTranscriptRepository,
    SQLiteVoiceSampleRepository,
)

from .settings import NoteKeeperSettings


@dataclass(frozen=True, slots=True)
class InfrastructureBundle:
    settings: NoteKeeperSettings
    database: SQLiteDatabase
    artifact_storage: LocalCampaignArtifactStorage
    folder_scanner: LocalCampaignFolderScanner
    metadata_reader: LocalAudioMetadataReader
    campaign_repository: SQLiteCampaignRepository
    participant_repository: SQLiteParticipantRepository
    voice_sample_repository: SQLiteVoiceSampleRepository
    audio_track_repository: SQLiteAudioTrackRepository
    transcript_repository: SQLiteTranscriptRepository
    recap_repository: SQLiteRecapRepository
    job_repository: SQLiteJobRepository
    clock: SystemClock
    id_generator: UuidGenerator


def build_infrastructure(
    settings: NoteKeeperSettings | None = None,
) -> InfrastructureBundle:
    resolved_settings = settings or NoteKeeperSettings()
    database = SQLiteDatabase(resolved_settings.sqlite_path)
    database.initialize()

    artifact_storage = LocalCampaignArtifactStorage(resolved_settings.storage_root)
    folder_scanner = LocalCampaignFolderScanner(
        artifact_storage,
        audio_extensions=resolved_settings.audio_extensions,
    )
    metadata_reader = LocalAudioMetadataReader(
        artifact_storage,
        ffprobe_path=resolved_settings.ffprobe_path,
    )

    return InfrastructureBundle(
        settings=resolved_settings,
        database=database,
        artifact_storage=artifact_storage,
        folder_scanner=folder_scanner,
        metadata_reader=metadata_reader,
        campaign_repository=SQLiteCampaignRepository(database),
        participant_repository=SQLiteParticipantRepository(database),
        voice_sample_repository=SQLiteVoiceSampleRepository(database),
        audio_track_repository=SQLiteAudioTrackRepository(database),
        transcript_repository=SQLiteTranscriptRepository(database, artifact_storage),
        recap_repository=SQLiteRecapRepository(database, artifact_storage),
        job_repository=SQLiteJobRepository(database),
        clock=SystemClock(),
        id_generator=UuidGenerator(),
    )
