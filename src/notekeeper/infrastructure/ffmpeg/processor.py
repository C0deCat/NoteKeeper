"""FFmpeg audio preparation adapter."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from notekeeper.application.ports import (
    AudioProcessor,
    PreparedAudioManifestStore,
    ProgressTracker,
)
from notekeeper.application.results import (
    PreparedAudioResult,
    PreparedVoiceSampleRange,
)
from notekeeper.domain import (
    ArtifactRef,
    AudioTrack,
    ProcessingJobId,
    ProcessingStage,
    TimeRange,
    VoiceSample,
)
from notekeeper.infrastructure.errors import InfrastructureError
from notekeeper.infrastructure.filesystem.storage import LocalCampaignArtifactStorage
from notekeeper.infrastructure.filesystem.utils import safe_name, sha256


class FfmpegAudioProcessor(AudioProcessor):
    def __init__(
        self,
        storage: LocalCampaignArtifactStorage,
        manifest_store: PreparedAudioManifestStore,
        *,
        ffmpeg_path: str = "ffmpeg",
        processing_work_root: str | Path | None = None,
        sample_rate_hz: int = 16000,
        channels: int = 1,
        codec: str = "pcm_s16le",
        container: str = "wav",
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if sample_rate_hz <= 0:
            raise InfrastructureError("sample_rate_hz must be positive")
        if channels <= 0:
            raise InfrastructureError("channels must be positive")

        executable = ffmpeg_path.strip()
        if not executable:
            raise InfrastructureError("ffmpeg_path must not be empty")

        self._storage = storage
        self._manifest_store = manifest_store
        self._ffmpeg_path = executable
        processing_root = Path(
            processing_work_root
            if processing_work_root is not None
            else storage.storage_root / "_work" / "ffmpeg",
        )
        self._processing_work_root = processing_root
        self._sample_rate_hz = sample_rate_hz
        self._channels = channels
        self._codec = safe_name(codec, "codec")
        self._container = safe_name(container.removeprefix("."), "container")
        self._now = now or (lambda: datetime.now(timezone.utc))

    def prepare_session_audio(
        self,
        audio_track: AudioTrack,
        voice_samples: tuple[VoiceSample, ...],
        *,
        job_id: ProcessingJobId,
        progress: ProgressTracker | None = None,
    ) -> PreparedAudioResult:
        voice_samples = tuple(voice_samples)
        self._ensure_campaign_consistency(audio_track, voice_samples)

        session_path = self._require_artifact_path(
            audio_track.artifact,
            "session audio",
        )
        sample_paths = [
            self._require_artifact_path(sample.artifact, "voice sample")
            for sample in voice_samples
        ]

        campaign_name = safe_name(str(audio_track.campaign_id), "campaign_id")
        job_name = safe_name(str(job_id), "job_id")
        work_dir = self._processing_work_root / campaign_name / job_name
        work_dir.mkdir(parents=True, exist_ok=True)

        prepared_uri = self._prepared_uri(campaign_name, job_name)
        prepared_path = self._storage.path_for_uri(prepared_uri)
        prepared_path.parent.mkdir(parents=True, exist_ok=True)

        command_metadata: list[dict[str, Any]] = []
        total_duration = sum(
            sample.metadata.duration_seconds for sample in voice_samples
        )
        normalized_duration = 0.0
        if progress is not None:
            progress.start_stage(
                ProcessingStage.NORMALIZING_AUDIO,
                timing_available=True,
            )
        normalized_sample_paths: list[Path] = []
        for index, (sample, sample_path) in enumerate(
            zip(voice_samples, sample_paths, strict=True),
            start=1,
        ):
            normalized_sample_path = (
                work_dir / f"normalized-sample-{index}.{self._container}"
            )
            command_metadata.append(
                self._normalize_audio(
                    source_path=sample_path,
                    output_path=normalized_sample_path,
                    source_artifact=sample.artifact,
                    source_role="voice_sample",
                    duration_seconds=sample.metadata.duration_seconds,
                    completed_duration_seconds=normalized_duration,
                    total_duration_seconds=total_duration,
                    progress=progress,
                ),
            )
            normalized_duration += sample.metadata.duration_seconds
            normalized_sample_paths.append(normalized_sample_path)

        if progress is not None:
            progress.complete_stage()
            progress.start_stage(
                ProcessingStage.CONCATENATING_AUDIO,
                timing_available=True,
            )
        command_metadata.append(
            self._concatenate_audio(
                input_paths=(session_path, *normalized_sample_paths),
                output_path=prepared_path,
                output_artifact_uri=prepared_uri,
                work_dir=work_dir,
                duration_seconds=total_duration,
                progress=progress,
            ),
        )
        if progress is not None:
            progress.complete_stage()

        prepared_artifact = ArtifactRef(
            uri=self._storage.uri_for_path(prepared_path),
            kind="file",
            checksum=sha256(prepared_path),
        )
        session_time_range = TimeRange(
            start_seconds=0,
            end_seconds=audio_track.metadata.duration_seconds,
        )
        sample_ranges = self._build_sample_ranges(
            session_duration=audio_track.metadata.duration_seconds,
            voice_samples=voice_samples,
        )
        prepared_total_duration = (
            session_time_range.duration_seconds
            + sum(
                sample_range.time_range.duration_seconds
                for sample_range in sample_ranges
            )
        )

        manifest_payload = self._build_manifest_payload(
            audio_track=audio_track,
            job_id=job_id,
            prepared_artifact=prepared_artifact,
            session_time_range=session_time_range,
            sample_ranges=sample_ranges,
            total_duration_seconds=prepared_total_duration,
            command_metadata=command_metadata,
        )
        manifest_artifact = self._manifest_store.save(
            campaign_id=audio_track.campaign_id,
            job_id=job_id,
            payload=manifest_payload,
        )

        return PreparedAudioResult(
            audio_artifact=prepared_artifact,
            manifest_artifact=manifest_artifact,
            source_audio_artifact=audio_track.artifact,
            session_time_range=session_time_range,
            voice_sample_ranges=sample_ranges,
        )

    def _normalize_audio(
        self,
        *,
        source_path: Path,
        output_path: Path,
        source_artifact: ArtifactRef,
        source_role: str,
        duration_seconds: float,
        completed_duration_seconds: float,
        total_duration_seconds: float,
        progress: ProgressTracker | None,
    ) -> dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
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
            *self._progress_arguments(),
            str(output_path),
        ]
        returncode = self._run_ffmpeg(
            command,
            f"normalize {source_role}",
            duration_seconds=duration_seconds,
            progress_callback=(
                lambda fraction: progress.update_fraction(
                    (
                        completed_duration_seconds
                        + duration_seconds * fraction
                    )
                    / total_duration_seconds
                )
                if progress is not None
                else None
            )
            if progress is not None and total_duration_seconds > 0
            else None,
        )
        self._require_output_file(output_path, f"normalized {source_role} audio")
        return {
            "stage": "normalize",
            "source_role": source_role,
            "source_artifact": self._artifact_to_dict(source_artifact),
            "arguments_template": [
                "-y",
                "-i",
                "<input>",
                "-vn",
                "-ac",
                str(self._channels),
                "-ar",
                str(self._sample_rate_hz),
                "-c:a",
                self._codec,
                "<output>",
            ],
            "returncode": returncode,
        }

    def _concatenate_audio(
        self,
        *,
        input_paths: tuple[Path, ...],
        output_path: Path,
        output_artifact_uri: str,
        work_dir: Path,
        duration_seconds: float,
        progress: ProgressTracker | None,
    ) -> dict[str, Any]:
        concat_list_path = work_dir / "concat.txt"
        concat_list_path.write_text(
            "\n".join(
                f"file '{self._concat_file_path(input_path)}'"
                for input_path in input_paths
            )
            + "\n",
            encoding="utf-8",
        )
        command = [
            self._ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list_path),
            "-c",
            "copy",
            *self._progress_arguments(),
            str(output_path),
        ]
        returncode = self._run_ffmpeg(
            command,
            "concatenate prepared audio",
            duration_seconds=duration_seconds,
            progress_callback=(
                progress.update_fraction if progress is not None else None
            ),
        )
        self._require_output_file(output_path, "prepared audio")
        return {
            "stage": "concat",
            "input_count": len(input_paths),
            "output_artifact_uri": output_artifact_uri,
            "arguments_template": [
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                "<concat_list>",
                "-c",
                "copy",
                "<output>",
            ],
            "returncode": returncode,
        }

    def _run_ffmpeg(
        self,
        command: list[str],
        stage: str,
        *,
        duration_seconds: float,
        progress_callback: Callable[[float], None] | None,
    ) -> int:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise InfrastructureError(
                f"ffmpeg executable not found during {stage}: {self._ffmpeg_path}",
            ) from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise InfrastructureError(
                f"ffmpeg command could not run during {stage}: {exc}",
            ) from exc

        assert process.stdout is not None
        for line in process.stdout:
            key, separator, value = line.strip().partition("=")
            if not separator:
                continue
            if key == "progress" and value == "end":
                if progress_callback is not None:
                    progress_callback(1.0)
                continue
            if key not in {"out_time_us", "out_time_ms"}:
                continue
            try:
                output_seconds = int(value) / 1_000_000
            except ValueError:
                continue
            if progress_callback is not None and duration_seconds > 0:
                progress_callback(min(output_seconds / duration_seconds, 1.0))

        stderr = process.stderr.read() if process.stderr is not None else ""
        returncode = process.wait()
        if returncode != 0:
            detail = stderr.strip()
            message = f"ffmpeg command failed during {stage}"
            if detail:
                message = f"{message}: {detail}"
            raise InfrastructureError(message)
        return returncode

    @staticmethod
    def _progress_arguments() -> list[str]:
        return [
            "-progress",
            "pipe:1",
            "-stats_period",
            "0.25",
            "-nostats",
            "-loglevel",
            "error",
        ]

    def _require_artifact_path(self, artifact: ArtifactRef, role: str) -> Path:
        path = self._storage.artifact_path(artifact)
        if not path.is_file():
            raise InfrastructureError(f"{role} artifact does not exist: {artifact.uri}")
        return path

    def _require_output_file(self, path: Path, role: str) -> None:
        if not path.is_file():
            raise InfrastructureError(f"ffmpeg did not create {role}: {path}")

    def _build_sample_ranges(
        self,
        *,
        session_duration: float,
        voice_samples: tuple[VoiceSample, ...],
    ) -> tuple[PreparedVoiceSampleRange, ...]:
        ranges = []
        offset = session_duration
        for sample in voice_samples:
            end = offset + sample.metadata.duration_seconds
            ranges.append(
                PreparedVoiceSampleRange(
                    source_artifact=sample.artifact,
                    voice_sample_id=sample.id,
                    participant_id=sample.participant_id,
                    time_range=TimeRange(offset, end),
                ),
            )
            offset = end
        return tuple(ranges)

    def _build_manifest_payload(
        self,
        *,
        audio_track: AudioTrack,
        job_id: ProcessingJobId,
        prepared_artifact: ArtifactRef,
        session_time_range: TimeRange,
        sample_ranges: tuple[PreparedVoiceSampleRange, ...],
        total_duration_seconds: float,
        command_metadata: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "job_id": str(job_id),
            "campaign_id": str(audio_track.campaign_id),
            "audio_track_id": str(audio_track.id),
            "created_at": self._now().isoformat(),
            "source_session_artifact": self._artifact_to_dict(audio_track.artifact),
            "prepared_artifact": self._artifact_to_dict(prepared_artifact),
            "session_offset_seconds": session_time_range.start_seconds,
            "session_time_range": self._time_range_to_dict(session_time_range),
            "total_duration_seconds": total_duration_seconds,
            "voice_sample_ranges": [
                {
                    "voice_sample_id": str(sample_range.voice_sample_id),
                    "participant_id": str(sample_range.participant_id),
                    "source_artifact": self._artifact_to_dict(
                        sample_range.source_artifact,
                    ),
                    "time_range": self._time_range_to_dict(sample_range.time_range),
                }
                for sample_range in sample_ranges
            ],
            "normalization": {
                "sample_rate_hz": self._sample_rate_hz,
                "channels": self._channels,
                "codec": self._codec,
                "container": self._container,
            },
            "ffmpeg_command_metadata": command_metadata,
        }

    def _ensure_campaign_consistency(
        self,
        audio_track: AudioTrack,
        voice_samples: tuple[VoiceSample, ...],
    ) -> None:
        for sample in voice_samples:
            if sample.campaign_id != audio_track.campaign_id:
                raise InfrastructureError(
                    "voice sample campaign does not match audio track campaign",
                )

    def _prepared_uri(self, campaign_name: str, job_name: str) -> str:
        return (
            f"{campaign_name}/records/transient/"
            f"{job_name}/prepared.{self._container}"
        )

    def _concat_file_path(self, path: Path) -> str:
        return path.resolve(strict=False).as_posix().replace("'", "'\\''")

    def _artifact_to_dict(self, artifact: ArtifactRef) -> dict[str, str | None]:
        return {
            "uri": artifact.uri,
            "kind": artifact.kind,
            "checksum": artifact.checksum,
        }

    def _time_range_to_dict(self, time_range: TimeRange) -> dict[str, float]:
        return {
            "start_seconds": time_range.start_seconds,
            "end_seconds": time_range.end_seconds,
        }
