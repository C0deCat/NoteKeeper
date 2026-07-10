"""WhisperX transcription adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from notekeeper.application.ports import Transcriber
from notekeeper.domain import (
    ArtifactRef,
    AudioTrackId,
    CampaignId,
    Transcript,
    TranscriptId,
)
from notekeeper.infrastructure.errors import InfrastructureError
from notekeeper.infrastructure.filesystem.storage import LocalCampaignArtifactStorage

from .interfaces import WhisperXPayloadStore, WhisperXRunner
from .payload_store import LocalWhisperXPayloadStore
from .runner import DefaultWhisperXRunner
from .utils import to_json_safe, transcript_from_whisperx_result


class WhisperXTranscriber(Transcriber):
    def __init__(
        self,
        storage: LocalCampaignArtifactStorage,
        payload_store: WhisperXPayloadStore | None = None,
        *,
        runner: WhisperXRunner | None = None,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        batch_size: int = 16,
        language: str | None = None,
        vad_method: str = "pyannote",
        alignment_enabled: bool = True,
        alignment_model_name: str | None = None,
        alignment_model_dir: str | Path | None = None,
        alignment_model_cache_only: bool = False,
        diarization_enabled: bool = True,
        diarization_model_name: str | None = None,
        diarization_cache_dir: str | Path | None = None,
        hf_token: str | None = None,
        fill_nearest: bool = False,
        unknown_speaker_label: str = "SPEAKER_UNKNOWN",
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._storage = storage
        self._payload_store = payload_store or LocalWhisperXPayloadStore(storage)
        self._runner = runner or DefaultWhisperXRunner()
        self._model_name = self._require_text(model_name, "model_name")
        self._device = self._require_text(device, "device")
        self._compute_type = self._require_text(compute_type, "compute_type")
        self._batch_size = self._require_positive_int(batch_size, "batch_size")
        self._language = self._optional_text(language, "language")
        self._vad_method = self._require_text(vad_method, "vad_method")
        self._alignment_enabled = alignment_enabled
        self._alignment_model_name = self._optional_text(
            alignment_model_name,
            "alignment_model_name",
        )
        self._alignment_model_dir = self._optional_path(alignment_model_dir)
        self._alignment_model_cache_only = alignment_model_cache_only
        self._diarization_enabled = diarization_enabled
        self._diarization_model_name = self._optional_text(
            diarization_model_name,
            "diarization_model_name",
        )
        self._diarization_cache_dir = self._optional_path(diarization_cache_dir)
        self._hf_token = self._optional_text(hf_token, "hf_token")
        self._fill_nearest = fill_nearest
        self._unknown_speaker_label = self._require_text(
            unknown_speaker_label,
            "unknown_speaker_label",
        )
        self._now = now or (lambda: datetime.now(timezone.utc))

    def transcribe(
        self,
        audio: ArtifactRef,
        *,
        transcript_id: TranscriptId,
        campaign_id: CampaignId,
        audio_track_id: AudioTrackId,
    ) -> Transcript:
        audio_path = self._require_audio_path(audio)
        payload = self._run_whisperx(audio_path)
        payload_artifact = self._save_payload(
            audio=audio,
            transcript_id=transcript_id,
            campaign_id=campaign_id,
            audio_track_id=audio_track_id,
            payload=payload,
        )

        final_result = payload.get("final")
        if not isinstance(final_result, dict):
            raise InfrastructureError(
                f"WhisperX payload is missing final result: {payload_artifact.uri}",
            )

        try:
            return transcript_from_whisperx_result(
                final_result,
                transcript_id=transcript_id,
                campaign_id=campaign_id,
                audio_track_id=audio_track_id,
                unknown_speaker_label=self._unknown_speaker_label,
            )
        except InfrastructureError as exc:
            raise InfrastructureError(
                f"could not convert WhisperX payload {payload_artifact.uri}: {exc}",
            ) from exc

    def _run_whisperx(self, audio_path: Path) -> dict[str, Any]:
        try:
            payload = self._runner.run(
                audio_path,
                model_name=self._model_name,
                device=self._device,
                compute_type=self._compute_type,
                batch_size=self._batch_size,
                language=self._language,
                vad_method=self._vad_method,
                alignment_enabled=self._alignment_enabled,
                alignment_model_name=self._alignment_model_name,
                alignment_model_dir=self._alignment_model_dir,
                alignment_model_cache_only=self._alignment_model_cache_only,
                diarization_enabled=self._diarization_enabled,
                diarization_model_name=self._diarization_model_name,
                diarization_cache_dir=self._diarization_cache_dir,
                hf_token=self._hf_token,
                fill_nearest=self._fill_nearest,
            )
        except InfrastructureError:
            raise
        except Exception as exc:
            raise InfrastructureError("WhisperX transcription failed") from exc

        if not isinstance(payload, dict):
            raise InfrastructureError("WhisperX runner must return a JSON object")
        return to_json_safe(payload)

    def _save_payload(
        self,
        *,
        audio: ArtifactRef,
        transcript_id: TranscriptId,
        campaign_id: CampaignId,
        audio_track_id: AudioTrackId,
        payload: dict[str, Any],
    ) -> ArtifactRef:
        return self._payload_store.save(
            campaign_id=campaign_id,
            transcript_id=transcript_id,
            payload={
                "schema_version": 1,
                "created_at": self._now().isoformat(),
                "campaign_id": str(campaign_id),
                "audio_track_id": str(audio_track_id),
                "transcript_id": str(transcript_id),
                "audio_artifact": self._artifact_to_dict(audio),
                "config": self._config_metadata(),
                "whisperx": payload,
            },
        )

    def _require_audio_path(self, artifact: ArtifactRef) -> Path:
        path = self._storage.artifact_path(artifact)
        if not path.is_file():
            raise InfrastructureError(
                f"prepared audio artifact does not exist: {artifact.uri}",
            )
        return path

    def _config_metadata(self) -> dict[str, Any]:
        return {
            "model_name": self._model_name,
            "device": self._device,
            "compute_type": self._compute_type,
            "batch_size": self._batch_size,
            "language": self._language,
            "vad_method": self._vad_method,
            "alignment": {
                "enabled": self._alignment_enabled,
                "model_name": self._alignment_model_name,
                "model_dir": (
                    str(self._alignment_model_dir)
                    if self._alignment_model_dir is not None
                    else None
                ),
                "model_cache_only": self._alignment_model_cache_only,
            },
            "diarization": {
                "enabled": self._diarization_enabled,
                "model_name": self._diarization_model_name,
                "cache_dir": (
                    str(self._diarization_cache_dir)
                    if self._diarization_cache_dir is not None
                    else None
                ),
                "hf_token": "<redacted>" if self._hf_token is not None else None,
            },
            "speaker_assignment": {
                "fill_nearest": self._fill_nearest,
                "unknown_speaker_label": self._unknown_speaker_label,
            },
        }

    def _artifact_to_dict(self, artifact: ArtifactRef) -> dict[str, str | None]:
        return {
            "uri": artifact.uri,
            "kind": artifact.kind,
            "checksum": artifact.checksum,
        }

    def _require_text(self, value: str, field: str) -> str:
        text = value.strip()
        if not text:
            raise InfrastructureError(f"{field} must not be empty")
        return text

    def _optional_text(self, value: str | None, field: str) -> str | None:
        if value is None:
            return None
        return self._require_text(value, field)

    def _require_positive_int(self, value: int, field: str) -> int:
        if not isinstance(value, int) or value <= 0:
            raise InfrastructureError(f"{field} must be a positive integer")
        return value

    def _optional_path(self, value: str | Path | None) -> Path | None:
        return Path(value) if value is not None else None


__all__ = ["WhisperXTranscriber"]
