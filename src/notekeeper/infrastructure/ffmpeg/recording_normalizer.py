"""FFmpeg adapter for canonical recording normalization."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

from notekeeper.application.ports import AudioRecordingNormalizer
from notekeeper.application.results import NormalizedAudioResult
from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrackId,
    CampaignId,
)
from notekeeper.infrastructure.errors import InfrastructureError
from notekeeper.infrastructure.filesystem.storage import LocalCampaignArtifactStorage
from notekeeper.infrastructure.filesystem.utils import read_audio_metadata, safe_name


class FfmpegRecordingNormalizer(AudioRecordingNormalizer):
    def __init__(
        self,
        storage: LocalCampaignArtifactStorage,
        *,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
        sample_rate_hz: int = 16000,
        channels: int = 1,
        codec: str = "pcm_s16le",
        container: str = "wav",
    ) -> None:
        if sample_rate_hz <= 0 or channels <= 0:
            raise InfrastructureError("normalization audio settings must be positive")
        executable = ffmpeg_path.strip()
        if not executable:
            raise InfrastructureError("ffmpeg_path must not be empty")

        self._storage = storage
        self._ffmpeg_path = executable
        self._ffprobe_path = ffprobe_path
        self._sample_rate_hz = sample_rate_hz
        self._channels = channels
        self._codec = safe_name(codec, "codec")
        self._container = safe_name(container.removeprefix("."), "container")

    def normalize_artifact(
        self,
        *,
        campaign_id: CampaignId,
        audio_track_id: AudioTrackId,
        source_artifact: ArtifactRef,
        source_metadata: AudioMetadata,
    ) -> NormalizedAudioResult:
        source_path = self._storage.artifact_path(source_artifact)
        return self._normalize(
            campaign_id=campaign_id,
            audio_track_id=audio_track_id,
            source_path=source_path,
            source_metadata=source_metadata,
            source_artifact=source_artifact,
        )

    def normalize_source(
        self,
        *,
        campaign_id: CampaignId,
        audio_track_id: AudioTrackId,
        source_path: Path,
        source_metadata: AudioMetadata,
    ) -> NormalizedAudioResult:
        return self._normalize(
            campaign_id=campaign_id,
            audio_track_id=audio_track_id,
            source_path=source_path.expanduser().resolve(strict=False),
            source_metadata=source_metadata,
            source_artifact=None,
        )

    def find_for_source(
        self,
        *,
        campaign_id: CampaignId,
        source_artifact: ArtifactRef,
        source_metadata: AudioMetadata,
    ) -> NormalizedAudioResult | None:
        normalized_dir = (
            self._storage.campaign_path(campaign_id) / "records" / "normalized"
        )
        if not normalized_dir.is_dir():
            return None
        for manifest_path in normalized_dir.glob("*.json"):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (
                payload.get("source_checksum") != source_metadata.checksum
                or payload.get("source_artifact_uri") != source_artifact.uri
            ):
                continue
            audio_track_id = AudioTrackId(str(payload.get("audio_track_id") or ""))
            audio_uri = str(payload.get("normalized_artifact_uri") or "")
            if not audio_track_id or not audio_uri:
                continue
            audio_artifact = ArtifactRef(uri=audio_uri, kind="file")
            if not self._storage.artifact_exists(audio_artifact):
                continue
            metadata = read_audio_metadata(
                self._storage.artifact_path(audio_artifact),
                self._ffprobe_path,
            )
            return NormalizedAudioResult(
                audio_track_id=audio_track_id,
                audio_artifact=ArtifactRef(
                    uri=audio_uri,
                    kind="file",
                    checksum=metadata.checksum,
                ),
                manifest_artifact=ArtifactRef(
                    uri=self._storage.uri_for_path(manifest_path),
                    kind="file",
                ),
                metadata=metadata,
                source_checksum=source_metadata.checksum,
                source_size_bytes=source_metadata.file_size_bytes or 0,
                normalized_size_bytes=metadata.file_size_bytes or 0,
            )
        return None

    def _normalize(
        self,
        *,
        campaign_id: CampaignId,
        audio_track_id: AudioTrackId,
        source_path: Path,
        source_metadata: AudioMetadata,
        source_artifact: ArtifactRef | None,
    ) -> NormalizedAudioResult:
        if not source_path.is_file():
            raise InfrastructureError(f"source file does not exist: {source_path}")

        campaign_name = safe_name(str(campaign_id), "campaign_id")
        track_name = safe_name(str(audio_track_id), "audio_track_id")
        normalized_uri = (
            f"{campaign_name}/records/normalized/{track_name}.{self._container}"
        )
        normalized_path = self._storage.path_for_uri(normalized_uri)
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = normalized_path.with_name(
            f".{track_name}.{uuid.uuid4().hex}.tmp.{self._container}",
        )

        command = [
            self._ffmpeg_path,
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            str(self._channels),
            "-ar",
            str(self._sample_rate_hz),
            "-c:a",
            self._codec,
            "-nostats",
            "-loglevel",
            "error",
            str(temp_path),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except FileNotFoundError as exc:
            raise InfrastructureError(
                f"ffmpeg executable not found: {self._ffmpeg_path}",
            ) from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise InfrastructureError("ffmpeg normalization could not run") from exc

        try:
            if completed.returncode != 0:
                detail = completed.stderr.strip()
                message = "ffmpeg recording normalization failed"
                if detail:
                    message = f"{message}: {detail}"
                raise InfrastructureError(message)
            if not temp_path.is_file():
                raise InfrastructureError("ffmpeg did not create normalized recording")

            metadata = read_audio_metadata(temp_path, self._ffprobe_path)
            os.replace(temp_path, normalized_path)
            audio_artifact = ArtifactRef(
                uri=self._storage.uri_for_path(normalized_path),
                kind="file",
                checksum=metadata.checksum,
            )
            manifest_artifact = self._write_manifest(
                campaign_id=campaign_id,
                audio_track_id=audio_track_id,
                audio_artifact=audio_artifact,
                source_artifact=source_artifact,
                source_metadata=source_metadata,
                normalized_metadata=metadata,
            )
            return NormalizedAudioResult(
                audio_track_id=audio_track_id,
                audio_artifact=audio_artifact,
                manifest_artifact=manifest_artifact,
                metadata=metadata,
                source_checksum=source_metadata.checksum,
                source_size_bytes=source_metadata.file_size_bytes or 0,
                normalized_size_bytes=metadata.file_size_bytes or 0,
            )
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _write_manifest(
        self,
        *,
        campaign_id: CampaignId,
        audio_track_id: AudioTrackId,
        audio_artifact: ArtifactRef,
        source_artifact: ArtifactRef | None,
        source_metadata: AudioMetadata,
        normalized_metadata: AudioMetadata,
    ) -> ArtifactRef:
        track_name = safe_name(str(audio_track_id), "audio_track_id")
        return self._storage.save_json_payload(
            campaign_id=campaign_id,
            folder="records",
            suggested_name=f"normalized/{track_name}.json",
            payload={
                "schema_version": 1,
                "campaign_id": str(campaign_id),
                "audio_track_id": str(audio_track_id),
                "source_artifact_uri": (
                    source_artifact.uri if source_artifact is not None else None
                ),
                "source_checksum": source_metadata.checksum,
                "source_size_bytes": source_metadata.file_size_bytes,
                "normalized_artifact_uri": audio_artifact.uri,
                "normalized_checksum": normalized_metadata.checksum,
                "normalized_size_bytes": normalized_metadata.file_size_bytes,
                "normalization": {
                    "sample_rate_hz": self._sample_rate_hz,
                    "channels": self._channels,
                    "codec": self._codec,
                    "container": self._container,
                },
            },
        )
