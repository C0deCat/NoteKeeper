"""Infrastructure composition factory."""

from __future__ import annotations

from dataclasses import dataclass

from notekeeper.application.ports import (
    AudioMetadataReader,
    AudioProcessor,
    AudioTrackRepository,
    CampaignArtifactStorage,
    CampaignFolderScanner,
    CampaignRepository,
    Clock,
    IdGenerator,
    JobRepository,
    ParticipantRepository,
    PreparedAudioManifestStore,
    RecapRepository,
    TranscriptRepository,
    VoiceSampleRepository,
)
from notekeeper.infrastructure.ffmpeg import FfmpegAudioProcessor
from notekeeper.infrastructure.filesystem import (
    LocalAudioMetadataReader,
    LocalCampaignArtifactStorage,
    LocalCampaignFolderScanner,
    LocalPreparedAudioManifestStore,
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
    artifact_storage: CampaignArtifactStorage
    folder_scanner: CampaignFolderScanner
    metadata_reader: AudioMetadataReader
    prepared_audio_manifest_store: PreparedAudioManifestStore
    audio_processor: AudioProcessor
    campaign_repository: CampaignRepository
    participant_repository: ParticipantRepository
    voice_sample_repository: VoiceSampleRepository
    audio_track_repository: AudioTrackRepository
    transcript_repository: TranscriptRepository
    recap_repository: RecapRepository
    job_repository: JobRepository
    clock: Clock
    id_generator: IdGenerator


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
    prepared_audio_manifest_store = LocalPreparedAudioManifestStore(artifact_storage)
    clock = SystemClock()
    id_generator = UuidGenerator()
    audio_processor = FfmpegAudioProcessor(
        artifact_storage,
        prepared_audio_manifest_store,
        ffmpeg_path=resolved_settings.ffmpeg_path,
        processing_work_root=resolved_settings.processing_work_root,
        sample_rate_hz=resolved_settings.prepared_audio_sample_rate_hz,
        channels=resolved_settings.prepared_audio_channels,
        codec=resolved_settings.prepared_audio_codec,
        container=resolved_settings.prepared_audio_container,
        now=clock.now,
    )

    return InfrastructureBundle(
        settings=resolved_settings,
        artifact_storage=artifact_storage,
        folder_scanner=folder_scanner,
        metadata_reader=metadata_reader,
        prepared_audio_manifest_store=prepared_audio_manifest_store,
        audio_processor=audio_processor,
        campaign_repository=SQLiteCampaignRepository(database),
        participant_repository=SQLiteParticipantRepository(database),
        voice_sample_repository=SQLiteVoiceSampleRepository(database),
        audio_track_repository=SQLiteAudioTrackRepository(database),
        transcript_repository=SQLiteTranscriptRepository(database, artifact_storage),
        recap_repository=SQLiteRecapRepository(database, artifact_storage),
        job_repository=SQLiteJobRepository(database),
        clock=clock,
        id_generator=id_generator,
    )
