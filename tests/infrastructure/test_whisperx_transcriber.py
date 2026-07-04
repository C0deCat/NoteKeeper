from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from notekeeper.domain import (
    ArtifactRef,
    AudioTrackId,
    CampaignId,
    SpeakerLabel,
    TranscriptId,
)
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.filesystem import LocalCampaignArtifactStorage
from notekeeper.infrastructure.whisperx import (
    LocalWhisperXPayloadStore,
    WhisperXTranscriber,
)
from notekeeper.infrastructure.whisperx.utils import transcript_from_whisperx_result


class FakeWhisperXRunner:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or _payload()
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        audio_path: Path,
        *,
        model_name: str,
        device: str,
        compute_type: str,
        batch_size: int,
        language: str | None,
        alignment_enabled: bool,
        alignment_model_name: str | None,
        alignment_model_dir: Path | None,
        alignment_model_cache_only: bool,
        diarization_enabled: bool,
        diarization_model_name: str | None,
        diarization_cache_dir: Path | None,
        hf_token: str | None,
        fill_nearest: bool,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "audio_path": audio_path,
                "model_name": model_name,
                "device": device,
                "compute_type": compute_type,
                "batch_size": batch_size,
                "language": language,
                "alignment_enabled": alignment_enabled,
                "alignment_model_name": alignment_model_name,
                "alignment_model_dir": alignment_model_dir,
                "alignment_model_cache_only": alignment_model_cache_only,
                "diarization_enabled": diarization_enabled,
                "diarization_model_name": diarization_model_name,
                "diarization_cache_dir": diarization_cache_dir,
                "hf_token": hf_token,
                "fill_nearest": fill_nearest,
            },
        )
        return self.payload


class FailingWhisperXRunner:
    def run(self, *args, **kwargs) -> dict[str, Any]:
        raise RuntimeError("boom")


def test_whisperx_payload_conversion_preserves_segments() -> None:
    transcript = transcript_from_whisperx_result(
        {
            "segments": [
                {
                    "index": 7,
                    "start": 1.5,
                    "end": 3.25,
                    "speaker": "SPEAKER_02",
                    "text": "  Hello there  ",
                },
                {
                    "start": 4,
                    "end": 5,
                    "text": "No speaker here",
                },
                {
                    "start": 6,
                    "end": 7,
                    "speaker": "SPEAKER_03",
                    "text": "   ",
                },
            ],
        },
        transcript_id=TranscriptId("transcript-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
        unknown_speaker_label="SPEAKER_UNKNOWN",
    )

    assert transcript.segments[0].index == 7
    assert transcript.segments[0].time_range.start_seconds == 1.5
    assert transcript.segments[0].time_range.end_seconds == 3.25
    assert transcript.segments[0].speaker_label == SpeakerLabel.anonymous("SPEAKER_02")
    assert transcript.segments[0].text == "Hello there"
    assert transcript.segments[1].index == 1
    assert transcript.segments[1].speaker_label == SpeakerLabel.anonymous(
        "SPEAKER_UNKNOWN",
    )
    assert len(transcript.segments) == 2


def test_whisperx_payload_store_saves_and_reads_json(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    store = LocalWhisperXPayloadStore(storage)
    payload = {"schema_version": 1, "whisperx": {"final": {"segments": []}}}

    artifact = store.save(
        campaign_id=CampaignId("campaign-1"),
        transcript_id=TranscriptId("transcript-1"),
        payload=payload,
    )

    assert artifact.uri == "campaign-1/transcripts/raw-whisperx/transcript-1.json"
    assert store.read(artifact) == payload
    assert (tmp_path / artifact.uri).is_file()


def test_whisperx_transcriber_runs_fake_runner_and_persists_raw_payload(
    tmp_path: Path,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    audio = _prepared_audio(storage)
    payload_store = LocalWhisperXPayloadStore(storage)
    runner = FakeWhisperXRunner()
    transcriber = WhisperXTranscriber(
        storage,
        payload_store,
        runner=runner,
        model_name="tiny",
        device="cpu",
        compute_type="int8",
        batch_size=4,
        language="en",
        alignment_enabled=False,
        alignment_model_name="align-model",
        alignment_model_dir=tmp_path / "align-cache",
        alignment_model_cache_only=True,
        diarization_enabled=False,
        diarization_model_name="diar-model",
        diarization_cache_dir=tmp_path / "diar-cache",
        hf_token="secret-token",
        fill_nearest=True,
        now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    transcript = transcriber.transcribe(
        audio,
        transcript_id=TranscriptId("transcript-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
    )

    assert transcript.id == TranscriptId("transcript-1")
    assert [segment.text for segment in transcript.segments] == [
        "Alice speaks",
        "Bob answers",
    ]
    assert [segment.speaker_label.value for segment in transcript.segments] == [
        "SPEAKER_00",
        "SPEAKER_01",
    ]
    assert runner.calls[0]["audio_path"] == storage.artifact_path(audio)
    assert runner.calls[0]["alignment_enabled"] is False
    assert runner.calls[0]["diarization_enabled"] is False
    assert runner.calls[0]["fill_nearest"] is True

    payload_artifact = ArtifactRef(
        uri="campaign-1/transcripts/raw-whisperx/transcript-1.json",
    )
    raw_payload = payload_store.read(payload_artifact)
    assert raw_payload["created_at"] == "2026-01-01T00:00:00+00:00"
    assert raw_payload["audio_artifact"]["uri"] == audio.uri
    assert raw_payload["config"]["model_name"] == "tiny"
    assert raw_payload["config"]["diarization"]["hf_token"] == "<redacted>"
    assert "secret-token" not in json.dumps(raw_payload)
    assert raw_payload["whisperx"]["final"]["segments"][0]["text"] == "Alice speaks"


def test_whisperx_transcriber_wraps_runner_failures(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    transcriber = WhisperXTranscriber(
        storage,
        runner=FailingWhisperXRunner(),
    )

    with pytest.raises(InfrastructureError, match="WhisperX transcription failed"):
        transcriber.transcribe(
            _prepared_audio(storage),
            transcript_id=TranscriptId("transcript-1"),
            campaign_id=CampaignId("campaign-1"),
            audio_track_id=AudioTrackId("audio-track-1"),
        )


def test_whisperx_transcriber_rejects_missing_audio(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    transcriber = WhisperXTranscriber(storage, runner=FakeWhisperXRunner())

    with pytest.raises(
        InfrastructureError,
        match="prepared audio artifact does not exist",
    ):
        transcriber.transcribe(
            ArtifactRef(uri="campaign-1/records/prepared/missing.wav"),
            transcript_id=TranscriptId("transcript-1"),
            campaign_id=CampaignId("campaign-1"),
            audio_track_id=AudioTrackId("audio-track-1"),
        )


def test_whisperx_transcriber_rejects_invalid_final_payload(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    transcriber = WhisperXTranscriber(
        storage,
        runner=FakeWhisperXRunner(payload={"final": {"segments": "bad"}}),
    )

    with pytest.raises(
        InfrastructureError,
        match="could not convert WhisperX payload",
    ):
        transcriber.transcribe(
            _prepared_audio(storage),
            transcript_id=TranscriptId("transcript-1"),
            campaign_id=CampaignId("campaign-1"),
            audio_track_id=AudioTrackId("audio-track-1"),
        )


def _payload() -> dict[str, Any]:
    return {
        "asr": {
            "language": "en",
            "segments": [
                {"start": 0.0, "end": 1.25, "text": "Alice speaks"},
                {"start": 1.25, "end": 2.0, "text": "Bob answers"},
            ],
        },
        "alignment": None,
        "diarization": {
            "segments": [
                {"start": 0.0, "end": 1.25, "speaker": "SPEAKER_00"},
                {"start": 1.25, "end": 2.0, "speaker": "SPEAKER_01"},
            ],
        },
        "final": {
            "segments": [
                {
                    "start": 0.0,
                    "end": 1.25,
                    "speaker": "SPEAKER_00",
                    "text": "Alice speaks",
                },
                {
                    "start": 1.25,
                    "end": 2.0,
                    "speaker": "SPEAKER_01",
                    "text": "Bob answers",
                },
            ],
        },
    }


def _prepared_audio(storage: LocalCampaignArtifactStorage) -> ArtifactRef:
    path = storage.path_for_uri("campaign-1/records/prepared/job-1/prepared.wav")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"prepared audio")
    return ArtifactRef(uri="campaign-1/records/prepared/job-1/prepared.wav")
