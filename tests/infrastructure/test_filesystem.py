from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

from notekeeper.domain import ArtifactRef, CampaignId, ProcessingJobId
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.filesystem import (
    LocalAudioMetadataReader,
    LocalCampaignArtifactStorage,
    LocalCampaignFolderScanner,
    LocalPreparedAudioManifestStore,
    LocalSourceAudioMetadataReader,
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


def test_storage_delete_campaign_removes_only_its_campaign_folder(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    storage.ensure_campaign_layout(CampaignId("campaign-1"))
    storage.ensure_campaign_layout(CampaignId("campaign-2"))

    storage.delete_campaign(CampaignId("campaign-1"))

    assert not (tmp_path / "campaign-1").exists()
    assert (tmp_path / "campaign-2").is_dir()


def test_storage_rejects_unsafe_relative_uri(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)

    with pytest.raises(InfrastructureError):
        storage.path_for_uri("../outside.wav")

    with pytest.raises(InfrastructureError):
        storage.path_for_uri("file://campaign-1/records/session.wav")

    with pytest.raises(InfrastructureError):
        storage.path_for_uri("campaign-1\\records\\session.wav")


def test_storage_imports_file_and_resolves_name_collisions(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    source = tmp_path / "session.wav"
    source.write_bytes(b"audio")

    first = storage.import_file(
        campaign_id=CampaignId("campaign-1"),
        folder="records",
        source_path=source,
    )
    second = storage.import_file(
        campaign_id=CampaignId("campaign-1"),
        folder="records",
        source_path=source,
    )

    assert first.uri == "campaign-1/records/session.wav"
    assert second.uri == "campaign-1/records/session_1.wav"
    assert (tmp_path / "artifacts" / first.uri).read_bytes() == b"audio"
    assert source.read_bytes() == b"audio"


def test_storage_reuses_file_already_in_target_directory(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    storage.ensure_campaign_layout(CampaignId("campaign-1"))
    source = tmp_path / "campaign-1" / "records" / "session.wav"
    source.write_bytes(b"audio")

    artifact = storage.import_file(
        campaign_id=CampaignId("campaign-1"),
        folder="records",
        source_path=source,
    )

    assert artifact.uri == "campaign-1/records/session.wav"
    assert list(source.parent.glob("session*.wav")) == [source]


def test_prepared_audio_manifest_store_saves_and_reads_json(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    store = LocalPreparedAudioManifestStore(storage)
    payload = {
        "schema_version": 1,
        "prepared_artifact": {
            "uri": "campaign-1/records/transient/job-1/prepared.wav",
            "kind": "file",
        },
        "source_session_artifact": {
            "uri": "campaign-1/records/normalized/audio-track-1.wav",
            "kind": "file",
        },
    }

    artifact = store.save(
        campaign_id=CampaignId("campaign-1"),
        job_id=ProcessingJobId("job-1"),
        payload=payload,
    )

    assert artifact.uri == (
        "campaign-1/records/manifests/job-1/prepared-audio.json"
    )
    assert store.read(artifact) == payload
    raw_payload = json.loads((tmp_path / artifact.uri).read_text(encoding="utf-8"))
    assert raw_payload["prepared_artifact"]["uri"].startswith("campaign-1/")
    assert "://" not in raw_payload["prepared_artifact"]["uri"]


def test_prepared_audio_manifest_store_rejects_unsafe_job_path(
    tmp_path: Path,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    store = LocalPreparedAudioManifestStore(storage)

    with pytest.raises(InfrastructureError):
        store.save(
            campaign_id=CampaignId("campaign-1"),
            job_id=ProcessingJobId("../job-1"),
            payload={},
        )


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


def test_source_audio_metadata_reader_reads_absolute_wav_path(tmp_path: Path) -> None:
    wav_path = tmp_path / "source.wav"
    _write_wav(wav_path)

    metadata = LocalSourceAudioMetadataReader(
        ffprobe_path="missing-ffprobe",
    ).read(wav_path.resolve())

    assert metadata.duration_seconds == pytest.approx(0.1)
    assert metadata.file_size_bytes == wav_path.stat().st_size
    assert metadata.checksum is not None


def _write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 1600)
