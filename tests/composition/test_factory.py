from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import get_type_hints

import pytest

import notekeeper.composition.factory as factory_module
from notekeeper.application import PortExecutionError
from notekeeper.application.ports import (
    AudioMetadataReader,
    AudioProcessor,
    AudioTrackRepository,
    CampaignArtifactStorage,
    CampaignFolderScanner,
    CampaignRepository,
    Clock,
    IdGenerator,
    JobCleaner,
    JobRepository,
    ParticipantRepository,
    PreparedAudioManifestStore,
    ProgressEventSnapshotStore,
    RecapGenerator,
    RecapGuidances,
    RecapRepository,
    SpeakerIdentifier,
    SpeakerMappingRepository,
    SpeakerReviewSubmissionRepository,
    Tokenizer,
    Transcriber,
    TranscriptRepository,
    VoiceSampleRepository,
)
from notekeeper.composition import (
    LocalServices,
    NoteKeeperSettings,
    SystemRepositories,
    build_local_services,
)
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.cleanup import LocalJobCleaner
from notekeeper.infrastructure.deepseek import (
    DeepSeekRecapGenerator,
    LocalDeepSeekRequestLogger,
    NoOpDeepSeekRequestLogger,
)
from notekeeper.infrastructure.ffmpeg import FfmpegAudioProcessor
from notekeeper.infrastructure.filesystem import (
    JsonCampaignRecapGuidances,
    LocalAudioMetadataReader,
    LocalCampaignArtifactStorage,
    LocalCampaignFolderScanner,
    LocalPreparedAudioManifestStore,
)
from notekeeper.infrastructure.runtime import SystemClock, UuidGenerator
from notekeeper.infrastructure.speaker_mapping import SampleBasedSpeakerIdentifier
from notekeeper.infrastructure.sqlite import (
    SQLiteAudioTrackRepository,
    SQLiteCampaignRepository,
    SQLiteDatabase,
    SQLiteJobRepository,
    SQLiteParticipantRepository,
    SQLiteProgressEventSnapshotStore,
    SQLiteRecapRepository,
    SQLiteSpeakerMappingRepository,
    SQLiteSpeakerReviewSubmissionRepository,
    SQLiteTranscriptRepository,
    SQLiteVoiceSampleRepository,
)
from notekeeper.infrastructure.tokenization import TiktokenTranscriptTokenizer
from notekeeper.infrastructure.whisperx import WhisperXTranscriber


def test_local_services_groups_repositories_and_exposes_database_explicitly() -> None:
    hints = get_type_hints(LocalServices)

    assert {field.name for field in fields(LocalServices)} >= {
        "database",
        "repositories",
        "workspace_repository",
    }
    assert hints["settings"] is NoteKeeperSettings
    assert hints["database"] is SQLiteDatabase
    assert hints["repositories"] is SystemRepositories

    concrete_types = {
        FfmpegAudioProcessor,
        LocalAudioMetadataReader,
        LocalCampaignArtifactStorage,
        LocalCampaignFolderScanner,
        LocalPreparedAudioManifestStore,
        JsonCampaignRecapGuidances,
        LocalJobCleaner,
        SampleBasedSpeakerIdentifier,
        TiktokenTranscriptTokenizer,
        DeepSeekRecapGenerator,
        WhisperXTranscriber,
        SQLiteAudioTrackRepository,
        SQLiteCampaignRepository,
        SQLiteJobRepository,
        SQLiteParticipantRepository,
        SQLiteProgressEventSnapshotStore,
        SQLiteRecapRepository,
        SQLiteSpeakerMappingRepository,
        SQLiteSpeakerReviewSubmissionRepository,
        SQLiteTranscriptRepository,
        SQLiteVoiceSampleRepository,
        SystemClock,
        UuidGenerator,
    }
    non_boundary_hints = {
        value
        for name, value in hints.items()
        if name not in {"database", "repositories"}
    }
    assert concrete_types.isdisjoint(non_boundary_hints)


def test_infrastructure_implementations_inherit_ports() -> None:
    expected_ports = {
        LocalCampaignArtifactStorage: CampaignArtifactStorage,
        LocalCampaignFolderScanner: CampaignFolderScanner,
        LocalAudioMetadataReader: AudioMetadataReader,
        LocalPreparedAudioManifestStore: PreparedAudioManifestStore,
        JsonCampaignRecapGuidances: RecapGuidances,
        FfmpegAudioProcessor: AudioProcessor,
        WhisperXTranscriber: Transcriber,
        SampleBasedSpeakerIdentifier: SpeakerIdentifier,
        TiktokenTranscriptTokenizer: Tokenizer,
        DeepSeekRecapGenerator: RecapGenerator,
        LocalJobCleaner: JobCleaner,
        SQLiteCampaignRepository: CampaignRepository,
        SQLiteParticipantRepository: ParticipantRepository,
        SQLiteProgressEventSnapshotStore: ProgressEventSnapshotStore,
        SQLiteVoiceSampleRepository: VoiceSampleRepository,
        SQLiteAudioTrackRepository: AudioTrackRepository,
        SQLiteTranscriptRepository: TranscriptRepository,
        SQLiteRecapRepository: RecapRepository,
        SQLiteJobRepository: JobRepository,
        SQLiteSpeakerMappingRepository: SpeakerMappingRepository,
        SQLiteSpeakerReviewSubmissionRepository: SpeakerReviewSubmissionRepository,
        SystemClock: Clock,
        UuidGenerator: IdGenerator,
    }

    for implementation, port in expected_ports.items():
        assert port in implementation.__mro__


def test_infrastructure_error_is_port_execution_error() -> None:
    assert issubclass(InfrastructureError, PortExecutionError)


def test_build_local_services_wires_campaign_recap_guidances_without_loading_prompts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class CapturingRecapGenerator(RecapGenerator):
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def generate_chunk(self, chunk, *, guidance, context):
            return "chunk"

        def combine_chunks(self, chunks, *, guidance, context):
            return "combined"

    monkeypatch.setattr(
        factory_module,
        "DeepSeekRecapGenerator",
        CapturingRecapGenerator,
    )

    bundle = build_local_services(
        NoteKeeperSettings(
            storage_root=tmp_path / "artifacts",
            sqlite_path=tmp_path / "notekeeper.sqlite3",
            deepseek_api_key="secret-key",
        ),
    )

    assert isinstance(bundle.tokenizer, TiktokenTranscriptTokenizer)
    assert isinstance(bundle.recap_guidances, JsonCampaignRecapGuidances)
    assert isinstance(bundle.recap_generator, CapturingRecapGenerator)
    assert "chunk_recap_prompt" not in captured
    assert "combine_chunks_prompt" not in captured
    assert captured["api_key"] == "secret-key"
    assert isinstance(captured["request_logger"], NoOpDeepSeekRequestLogger)


def test_build_local_services_can_enable_deepseek_request_logging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class CapturingRecapGenerator(RecapGenerator):
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def generate_chunk(self, chunk, *, guidance, context):
            return "chunk"

        def combine_chunks(self, chunks, *, guidance, context):
            return "combined"

    monkeypatch.setattr(
        factory_module,
        "DeepSeekRecapGenerator",
        CapturingRecapGenerator,
    )

    build_local_services(
        NoteKeeperSettings(
            storage_root=tmp_path / "artifacts",
            sqlite_path=tmp_path / "notekeeper.sqlite3",
            deepseek_request_logging_enabled=True,
            deepseek_log_full_payloads=True,
        ),
    )

    assert isinstance(captured["request_logger"], LocalDeepSeekRequestLogger)


def test_build_local_services_configures_ffmpeg_dll_directory_on_windows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ffmpeg_bin = tmp_path / "ffmpeg" / "bin"
    configured_paths: list[str] = []

    class FakeDllDirectoryHandle:
        pass

    class CapturingRecapGenerator(RecapGenerator):
        def __init__(self, **kwargs) -> None:
            pass

        def generate_chunk(self, chunk, *, guidance, context):
            return "chunk"

        def combine_chunks(self, chunks, *, guidance, context):
            return "combined"

    monkeypatch.setattr(factory_module.os, "name", "nt")
    monkeypatch.setattr(
        factory_module.os,
        "add_dll_directory",
        lambda path: configured_paths.append(path) or FakeDllDirectoryHandle(),
    )
    monkeypatch.setattr(
        factory_module,
        "DeepSeekRecapGenerator",
        CapturingRecapGenerator,
    )
    monkeypatch.setattr(factory_module, "_CONFIGURED_FFMPEG_DLL_DIRECTORIES", set())
    monkeypatch.setattr(factory_module, "_FFMPEG_DLL_DIRECTORY_HANDLES", [])

    build_local_services(
        NoteKeeperSettings(
            storage_root=tmp_path / "artifacts",
            sqlite_path=tmp_path / "notekeeper.sqlite3",
            ffmpeg_bin=ffmpeg_bin,
        ),
    )

    assert configured_paths == [str(ffmpeg_bin.resolve(strict=False))]
    assert len(factory_module._FFMPEG_DLL_DIRECTORY_HANDLES) == 1


def test_build_local_services_skips_ffmpeg_dll_directory_without_setting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_paths: list[str] = []

    class CapturingRecapGenerator(RecapGenerator):
        def __init__(self, **kwargs) -> None:
            pass

        def generate_chunk(self, chunk, *, guidance, context):
            return "chunk"

        def combine_chunks(self, chunks, *, guidance, context):
            return "combined"

    monkeypatch.setattr(factory_module.os, "name", "nt")
    monkeypatch.setattr(
        factory_module.os,
        "add_dll_directory",
        lambda path: configured_paths.append(path),
    )
    monkeypatch.setattr(
        factory_module,
        "DeepSeekRecapGenerator",
        CapturingRecapGenerator,
    )

    build_local_services(
        NoteKeeperSettings(
            storage_root=tmp_path / "artifacts",
            sqlite_path=tmp_path / "notekeeper.sqlite3",
            ffmpeg_bin=None,
        ),
    )

    assert configured_paths == []
