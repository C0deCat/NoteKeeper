from __future__ import annotations

import json
import subprocess
import wave
from datetime import datetime, timezone
from pathlib import Path

import pytest

from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrack,
    AudioTrackId,
    CampaignId,
    ParticipantId,
    ProcessingJobId,
    VoiceSample,
    VoiceSampleId,
)
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.ffmpeg import FfmpegAudioProcessor
from notekeeper.infrastructure.filesystem import (
    LocalCampaignArtifactStorage,
    LocalPreparedAudioManifestStore,
)


def test_ffmpeg_audio_processor_prepares_audio_and_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    manifest_store = LocalPreparedAudioManifestStore(storage)
    audio_track = _audio_track(storage)
    voice_sample = _voice_sample(storage)
    calls: list[list[str]] = []

    def fake_run(command, check, capture_output, text):
        calls.append(command)
        _write_wav(Path(command[-1]))
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    processor = FfmpegAudioProcessor(
        storage,
        manifest_store,
        ffmpeg_path="fake-ffmpeg",
        processing_work_root=tmp_path / "work",
        now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    result = processor.prepare_session_audio(
        audio_track,
        (voice_sample,),
        job_id=ProcessingJobId("job-1"),
    )

    assert result.audio_artifact.uri == (
        "campaign-1/records/prepared/job-1/prepared.wav"
    )
    assert result.manifest_artifact.uri == (
        "campaign-1/records/prepared/job-1/manifest.json"
    )
    assert result.session_time_range.start_seconds == 0
    assert result.session_time_range.end_seconds == 3.0
    assert result.voice_sample_ranges[0].time_range.start_seconds == 3.0
    assert result.voice_sample_ranges[0].time_range.end_seconds == 4.25
    assert storage.artifact_path(result.audio_artifact).is_file()

    manifest = manifest_store.read(result.manifest_artifact)
    assert manifest["source_session_artifact"]["uri"] == audio_track.artifact.uri
    assert manifest["prepared_artifact"]["uri"] == result.audio_artifact.uri
    assert manifest["session_offset_seconds"] == 0
    assert manifest["total_duration_seconds"] == 4.25
    assert manifest["normalization"] == {
        "sample_rate_hz": 16000,
        "channels": 1,
        "codec": "pcm_s16le",
        "container": "wav",
    }
    assert [entry["stage"] for entry in manifest["ffmpeg_command_metadata"]] == [
        "normalize",
        "normalize",
        "concat",
    ]
    assert manifest["voice_sample_ranges"][0]["source_artifact"]["uri"] == (
        voice_sample.artifact.uri
    )
    assert str(tmp_path) not in json.dumps(manifest)
    assert len(calls) == 3
    assert calls[0][0] == "fake-ffmpeg"
    assert calls[0][calls[0].index("-ar") + 1] == "16000"


def test_ffmpeg_audio_processor_rejects_missing_session_artifact(
    tmp_path: Path,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    manifest_store = LocalPreparedAudioManifestStore(storage)
    processor = FfmpegAudioProcessor(
        storage,
        manifest_store,
        ffmpeg_path="fake-ffmpeg",
        processing_work_root=tmp_path / "work",
    )
    audio_track = AudioTrack(
        id=AudioTrackId("audio-track-1"),
        campaign_id=CampaignId("campaign-1"),
        artifact=ArtifactRef(uri="campaign-1/records/missing.wav"),
        metadata=AudioMetadata(duration_seconds=3.0),
    )

    with pytest.raises(InfrastructureError, match="session audio artifact does not exist"):
        processor.prepare_session_audio(
            audio_track,
            (),
            job_id=ProcessingJobId("job-1"),
        )


def test_ffmpeg_audio_processor_wraps_failed_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    manifest_store = LocalPreparedAudioManifestStore(storage)
    audio_track = _audio_track(storage)

    def fake_run(command, check, capture_output, text):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=command,
            stderr="boom",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    processor = FfmpegAudioProcessor(
        storage,
        manifest_store,
        ffmpeg_path="fake-ffmpeg",
        processing_work_root=tmp_path / "work",
    )

    with pytest.raises(
        InfrastructureError,
        match="ffmpeg command failed during normalize session: boom",
    ):
        processor.prepare_session_audio(
            audio_track,
            (),
            job_id=ProcessingJobId("job-1"),
        )


def _audio_track(storage: LocalCampaignArtifactStorage) -> AudioTrack:
    storage.ensure_campaign_layout(CampaignId("campaign-1"))
    path = storage.path_for_uri("campaign-1/records/session.wav")
    path.write_bytes(b"session")
    return AudioTrack(
        id=AudioTrackId("audio-track-1"),
        campaign_id=CampaignId("campaign-1"),
        artifact=ArtifactRef(uri="campaign-1/records/session.wav"),
        metadata=AudioMetadata(duration_seconds=3.0),
        title="Session",
    )


def _voice_sample(storage: LocalCampaignArtifactStorage) -> VoiceSample:
    sample_path = storage.path_for_uri("campaign-1/players/Alice/sample.wav")
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_bytes(b"sample")
    return VoiceSample(
        id=VoiceSampleId("sample-1"),
        campaign_id=CampaignId("campaign-1"),
        participant_id=ParticipantId("participant-1"),
        artifact=ArtifactRef(uri="campaign-1/players/Alice/sample.wav"),
        metadata=AudioMetadata(duration_seconds=1.25),
    )


def _write_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 160)
