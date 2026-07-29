from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

from notekeeper.domain import ArtifactRef, AudioTrackId, CampaignId
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.ffmpeg import FfmpegRecordingNormalizer
from notekeeper.infrastructure.filesystem import (
    LocalAudioMetadataReader,
    LocalCampaignArtifactStorage,
)


def test_recording_normalizer_creates_canonical_audio_and_manifest(
    tmp_path: Path,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    storage.ensure_campaign_layout(CampaignId("campaign-1"))
    source_path = storage.path_for_uri("campaign-1/records/session.wav")
    _write_stereo_wav(source_path)
    source_artifact = ArtifactRef(uri="campaign-1/records/session.wav")
    metadata_reader = LocalAudioMetadataReader(storage)
    source_metadata = metadata_reader.read(source_artifact)
    normalizer = FfmpegRecordingNormalizer(storage)

    result = normalizer.normalize_artifact(
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
        source_artifact=source_artifact,
        source_metadata=source_metadata,
    )

    assert result.audio_artifact.uri == (
        "campaign-1/records/normalized/audio-track-1.wav"
    )
    assert result.metadata.sample_rate_hz == 16000
    assert result.metadata.channels == 1
    assert result.metadata.codec == "pcm_s16le"
    assert source_path.is_file()
    assert storage.artifact_path(result.audio_artifact).is_file()
    manifest = json.loads(
        storage.artifact_path(result.manifest_artifact).read_text(encoding="utf-8"),
    )
    assert manifest["source_artifact_uri"] == source_artifact.uri
    assert manifest["source_checksum"] == source_metadata.checksum
    assert manifest["normalization"] == {
        "channels": 1,
        "codec": "pcm_s16le",
        "container": "wav",
        "sample_rate_hz": 16000,
    }
    assert not tuple(
        storage.artifact_path(result.audio_artifact).parent.glob("*.tmp.wav"),
    )


def test_recording_normalizer_failure_preserves_source(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    storage.ensure_campaign_layout(CampaignId("campaign-1"))
    source_path = storage.path_for_uri("campaign-1/records/session.wav")
    _write_stereo_wav(source_path)
    source_artifact = ArtifactRef(uri="campaign-1/records/session.wav")
    source_metadata = LocalAudioMetadataReader(storage).read(source_artifact)
    normalizer = FfmpegRecordingNormalizer(
        storage,
        ffmpeg_path="definitely-missing-ffmpeg",
    )

    with pytest.raises(InfrastructureError, match="ffmpeg executable not found"):
        normalizer.normalize_artifact(
            campaign_id=CampaignId("campaign-1"),
            audio_track_id=AudioTrackId("audio-track-1"),
            source_artifact=source_artifact,
            source_metadata=source_metadata,
        )

    assert source_path.is_file()
    assert not storage.path_for_uri(
        "campaign-1/records/normalized/audio-track-1.wav",
    ).exists()


def _write_stereo_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes(b"\x00\x00\x00\x00" * 9600)
