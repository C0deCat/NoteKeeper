from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import get_type_hints

import pytest

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
    RecapGenerator,
    RecapRepository,
    SpeakerIdentifier,
    SpeakerMappingRepository,
    Tokenizer,
    Transcriber,
    TranscriptRepository,
    VoiceSampleRepository,
)
import notekeeper.composition.factory as factory_module
from notekeeper.composition import (
    InfrastructureBundle,
    NoteKeeperSettings,
    build_infrastructure,
)
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.deepseek import DeepSeekRecapGenerator
from notekeeper.infrastructure.ffmpeg import FfmpegAudioProcessor
from notekeeper.infrastructure.filesystem import (
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
    SQLiteJobRepository,
    SQLiteParticipantRepository,
    SQLiteRecapRepository,
    SQLiteSpeakerMappingRepository,
    SQLiteTranscriptRepository,
    SQLiteVoiceSampleRepository,
)
from notekeeper.infrastructure.tokenization import TiktokenTranscriptTokenizer
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
        "speaker_identifier": SpeakerIdentifier,
        "tokenizer": Tokenizer,
        "recap_generator": RecapGenerator,
        "campaign_repository": CampaignRepository,
        "participant_repository": ParticipantRepository,
        "voice_sample_repository": VoiceSampleRepository,
        "audio_track_repository": AudioTrackRepository,
        "transcript_repository": TranscriptRepository,
        "recap_repository": RecapRepository,
        "job_repository": JobRepository,
        "speaker_mapping_repository": SpeakerMappingRepository,
        "clock": Clock,
        "id_generator": IdGenerator,
    }

    concrete_types = {
        FfmpegAudioProcessor,
        LocalAudioMetadataReader,
        LocalCampaignArtifactStorage,
        LocalCampaignFolderScanner,
        LocalPreparedAudioManifestStore,
        SampleBasedSpeakerIdentifier,
        TiktokenTranscriptTokenizer,
        DeepSeekRecapGenerator,
        WhisperXTranscriber,
        SQLiteAudioTrackRepository,
        SQLiteCampaignRepository,
        SQLiteJobRepository,
        SQLiteParticipantRepository,
        SQLiteRecapRepository,
        SQLiteSpeakerMappingRepository,
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
        SampleBasedSpeakerIdentifier: SpeakerIdentifier,
        TiktokenTranscriptTokenizer: Tokenizer,
        DeepSeekRecapGenerator: RecapGenerator,
        SQLiteCampaignRepository: CampaignRepository,
        SQLiteParticipantRepository: ParticipantRepository,
        SQLiteVoiceSampleRepository: VoiceSampleRepository,
        SQLiteAudioTrackRepository: AudioTrackRepository,
        SQLiteTranscriptRepository: TranscriptRepository,
        SQLiteRecapRepository: RecapRepository,
        SQLiteJobRepository: JobRepository,
        SQLiteSpeakerMappingRepository: SpeakerMappingRepository,
        SystemClock: Clock,
        UuidGenerator: IdGenerator,
    }

    for implementation, port in expected_ports.items():
        assert port in implementation.__mro__


def test_build_infrastructure_loads_recap_prompts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts_file = _prompt_file(tmp_path, "chunk prompt", "combine prompt")
    captured: dict[str, object] = {}

    class CapturingRecapGenerator(RecapGenerator):
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def generate_chunk(self, chunk):
            return "chunk"

        def combine_chunks(self, chunks):
            return "combined"

    monkeypatch.setattr(
        factory_module,
        "DeepSeekRecapGenerator",
        CapturingRecapGenerator,
    )

    bundle = build_infrastructure(
        NoteKeeperSettings(
            storage_root=tmp_path / "artifacts",
            sqlite_path=tmp_path / "notekeeper.sqlite3",
            recap_prompts_file=prompts_file,
            deepseek_api_key="secret-key",
        ),
    )

    assert isinstance(bundle.tokenizer, TiktokenTranscriptTokenizer)
    assert isinstance(bundle.recap_generator, CapturingRecapGenerator)
    assert captured["chunk_recap_prompt"] == "chunk prompt"
    assert captured["combine_chunks_prompt"] == "combine prompt"
    assert captured["api_key"] == "secret-key"


def test_build_infrastructure_rejects_missing_recap_prompts_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(InfrastructureError, match="recap prompts file does not exist"):
        build_infrastructure(
            NoteKeeperSettings(
                storage_root=tmp_path / "artifacts",
                sqlite_path=tmp_path / "notekeeper.sqlite3",
                recap_prompts_file=tmp_path / "missing.json",
            ),
        )


def test_build_infrastructure_rejects_malformed_recap_prompts_file(
    tmp_path: Path,
) -> None:
    prompts_file = tmp_path / "recap_prompts.json"
    prompts_file.write_text("[]", encoding="utf-8")

    with pytest.raises(InfrastructureError, match="must contain a JSON object"):
        build_infrastructure(
            NoteKeeperSettings(
                storage_root=tmp_path / "artifacts",
                sqlite_path=tmp_path / "notekeeper.sqlite3",
                recap_prompts_file=prompts_file,
            ),
        )


def _prompt_file(tmp_path: Path, chunk_prompt: str, combine_prompt: str) -> Path:
    prompts_file = tmp_path / "recap_prompts.json"
    prompts_file.write_text(
        json.dumps(
            {
                "chunk_recap_prompt": chunk_prompt,
                "combine_chunks_prompt": combine_prompt,
            },
        ),
        encoding="utf-8",
    )
    return prompts_file
