"""Prepared-audio range and manifest builders."""

from datetime import datetime
from typing import Any

from notekeeper.application.results import PreparedVoiceSampleRange
from notekeeper.domain import (
    ArtifactRef,
    AudioTrack,
    ProcessingJobId,
    TimeRange,
    VoiceSample,
)


def build_sample_ranges(
    *,
    session_duration: float,
    voice_samples: tuple[VoiceSample, ...],
) -> tuple[PreparedVoiceSampleRange, ...]:
    ranges: list[PreparedVoiceSampleRange] = []
    offset = session_duration
    for sample in voice_samples:
        end = offset + sample.metadata.duration_seconds
        ranges.append(
            PreparedVoiceSampleRange(
                source_artifact=sample.artifact,
                voice_sample_id=sample.id,
                participant_id=sample.participant_id,
                time_range=TimeRange(offset, end),
            )
        )
        offset = end
    return tuple(ranges)


def build_prepared_manifest_payload(
    *,
    audio_track: AudioTrack,
    job_id: ProcessingJobId,
    prepared_artifact: ArtifactRef,
    session_time_range: TimeRange,
    sample_ranges: tuple[PreparedVoiceSampleRange, ...],
    total_duration_seconds: float,
    command_metadata: list[dict[str, Any]],
    created_at: datetime,
    sample_rate_hz: int,
    channels: int,
    codec: str,
    container: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "job_id": str(job_id),
        "campaign_id": str(audio_track.campaign_id),
        "audio_track_id": str(audio_track.id),
        "created_at": created_at.isoformat(),
        "source_session_artifact": _artifact_payload(audio_track.artifact),
        "prepared_artifact": _artifact_payload(prepared_artifact),
        "session_offset_seconds": session_time_range.start_seconds,
        "session_time_range": _time_range_payload(session_time_range),
        "total_duration_seconds": total_duration_seconds,
        "voice_sample_ranges": [
            {
                "voice_sample_id": str(sample_range.voice_sample_id),
                "participant_id": str(sample_range.participant_id),
                "source_artifact": _artifact_payload(sample_range.source_artifact),
                "time_range": _time_range_payload(sample_range.time_range),
            }
            for sample_range in sample_ranges
        ],
        "normalization": {
            "sample_rate_hz": sample_rate_hz,
            "channels": channels,
            "codec": codec,
            "container": container,
        },
        "ffmpeg_command_metadata": command_metadata,
    }


def artifact_payload(artifact: ArtifactRef) -> dict[str, str | None]:
    return _artifact_payload(artifact)


def _artifact_payload(artifact: ArtifactRef) -> dict[str, str | None]:
    return {
        "uri": artifact.uri,
        "kind": artifact.kind,
        "checksum": artifact.checksum,
    }


def _time_range_payload(time_range: TimeRange) -> dict[str, float]:
    return {
        "start_seconds": time_range.start_seconds,
        "end_seconds": time_range.end_seconds,
    }


__all__ = ["artifact_payload", "build_prepared_manifest_payload", "build_sample_ranges"]

