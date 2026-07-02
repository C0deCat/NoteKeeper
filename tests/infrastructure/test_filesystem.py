from __future__ import annotations

import wave
from pathlib import Path

import pytest

from notekeeper.domain import ArtifactRef, CampaignId
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.filesystem import (
    LocalAudioMetadataReader,
    LocalCampaignArtifactStorage,
    LocalCampaignFolderScanner,
)


def test_storage_creates_campaign_layout_and_saves_campaign_text(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)

    storage.ensure_campaign_layout(CampaignId("campaign-1"))
    artifact = storage.save_campaign_text(
        campaign_id=CampaignId("campaign-1"),
        folder="transcripts",
        suggested_name="session-1.md",
        content="# Session",
        media_type="text/markdown",
    )

    assert artifact.uri == "campaign-1/transcripts/session-1.md"
    assert (tmp_path / "campaign-1" / "players").is_dir()
    assert (tmp_path / "campaign-1" / "records").is_dir()
    assert storage.read_text(artifact) == "# Session"


def test_storage_rejects_unsafe_relative_uri(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)

    with pytest.raises(InfrastructureError):
        storage.path_for_uri("../outside.wav")

    with pytest.raises(InfrastructureError):
        storage.path_for_uri("file://campaign-1/records/session.wav")

    with pytest.raises(InfrastructureError):
        storage.path_for_uri("campaign-1\\records\\session.wav")


def test_scanner_finds_player_samples_and_records_only(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    storage.ensure_campaign_layout(CampaignId("campaign-1"))
    alice_path = tmp_path / "campaign-1" / "players" / "Alice"
    alice_path.mkdir()
    (alice_path / "sample.wav").write_bytes(b"not real audio")
    (alice_path / "notes.txt").write_text("ignore", encoding="utf-8")
    (tmp_path / "campaign-1" / "records" / "session-1.mp3").write_bytes(b"audio")
    (tmp_path / "campaign-1" / "records" / "cover.png").write_bytes(b"image")

    snapshot = LocalCampaignFolderScanner(storage).scan(CampaignId("campaign-1"))

    assert [sample.player_name for sample in snapshot.voice_samples] == ["Alice"]
    assert [sample.artifact.uri for sample in snapshot.voice_samples] == [
        "campaign-1/players/Alice/sample.wav",
    ]
    assert [track.artifact.uri for track in snapshot.audio_tracks] == [
        "campaign-1/records/session-1.mp3",
    ]
    assert snapshot.audio_tracks[0].title == "session-1"


def test_local_audio_metadata_reader_reads_wav_metadata(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    storage.ensure_campaign_layout(CampaignId("campaign-1"))
    wav_path = tmp_path / "campaign-1" / "records" / "session.wav"
    _write_wav(wav_path)

    metadata = LocalAudioMetadataReader(storage, ffprobe_path="missing-ffprobe").read(
        ArtifactRef(uri="campaign-1/records/session.wav"),
    )

    assert metadata.duration_seconds == pytest.approx(0.1)
    assert metadata.sample_rate_hz == 16000
    assert metadata.channels == 1
    assert metadata.file_size_bytes == wav_path.stat().st_size
    assert metadata.checksum is not None


def _write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 1600)
