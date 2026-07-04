from __future__ import annotations

from dataclasses import fields
from typing import get_type_hints

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
    Transcriber,
    TranscriptRepository,
    VoiceSampleRepository,
)
from notekeeper.composition import InfrastructureBundle, NoteKeeperSettings
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
    SQLiteJobRepository,
    SQLiteParticipantRepository,
    SQLiteRecapRepository,
    SQLiteTranscriptRepository,
    SQLiteVoiceSampleRepository,
)
from notekeeper.infrastructure.whisperx import WhisperXTranscriber


def test_infrastructure_bundle_uses_port_types_only() -> None:
    hints = get_type_hints(InfrastructureBundle)

    assert "database" not in {field.name for field in fields(InfrastructureBundle)}
    assert hints == {
        "settings": NoteKeeperSettings,
        "artifact_storage": CampaignArtifactStorage,
        "folder_scanner": CampaignFolderScanner,
        "metadata_reader": AudioMetadataReader,
        "prepared_audio_manifest_store": PreparedAudioManifestStore,
        "audio_processor": AudioProcessor,
        "transcriber": Transcriber,
        "campaign_repository": CampaignRepository,
        "participant_repository": ParticipantRepository,
        "voice_sample_repository": VoiceSampleRepository,
        "audio_track_repository": AudioTrackRepository,
        "transcript_repository": TranscriptRepository,
        "recap_repository": RecapRepository,
        "job_repository": JobRepository,
        "clock": Clock,
        "id_generator": IdGenerator,
    }

    concrete_types = {
        FfmpegAudioProcessor,
        LocalAudioMetadataReader,
        LocalCampaignArtifactStorage,
        LocalCampaignFolderScanner,
        LocalPreparedAudioManifestStore,
        WhisperXTranscriber,
        SQLiteAudioTrackRepository,
        SQLiteCampaignRepository,
        SQLiteJobRepository,
        SQLiteParticipantRepository,
        SQLiteRecapRepository,
        SQLiteTranscriptRepository,
        SQLiteVoiceSampleRepository,
        SystemClock,
        UuidGenerator,
    }
    assert concrete_types.isdisjoint(hints.values())


def test_infrastructure_implementations_inherit_ports() -> None:
    expected_ports = {
        LocalCampaignArtifactStorage: CampaignArtifactStorage,
        LocalCampaignFolderScanner: CampaignFolderScanner,
        LocalAudioMetadataReader: AudioMetadataReader,
        LocalPreparedAudioManifestStore: PreparedAudioManifestStore,
        FfmpegAudioProcessor: AudioProcessor,
        WhisperXTranscriber: Transcriber,
        SQLiteCampaignRepository: CampaignRepository,
        SQLiteParticipantRepository: ParticipantRepository,
        SQLiteVoiceSampleRepository: VoiceSampleRepository,
        SQLiteAudioTrackRepository: AudioTrackRepository,
        SQLiteTranscriptRepository: TranscriptRepository,
        SQLiteRecapRepository: RecapRepository,
        SQLiteJobRepository: JobRepository,
        SystemClock: Clock,
        UuidGenerator: IdGenerator,
    }

    for implementation, port in expected_ports.items():
        assert port in implementation.__mro__
