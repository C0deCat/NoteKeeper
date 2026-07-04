"""WhisperX transcript segment conversion helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from notekeeper.domain import (
    AudioTrackId,
    CampaignId,
    DomainValidationError,
    SpeakerLabel,
    TimeRange,
    Transcript,
    TranscriptId,
    TranscriptSegment,
)
from notekeeper.infrastructure.errors import InfrastructureError


def transcript_from_whisperx_result(
    result: dict[str, Any],
    *,
    transcript_id: TranscriptId,
    campaign_id: CampaignId,
    audio_track_id: AudioTrackId,
    unknown_speaker_label: str,
) -> Transcript:
    segments = _segments_from_result(result, unknown_speaker_label)
    return Transcript(
        id=transcript_id,
        campaign_id=campaign_id,
        audio_track_id=audio_track_id,
        segments=segments,
    )


def _segments_from_result(
    result: dict[str, Any],
    unknown_speaker_label: str,
) -> tuple[TranscriptSegment, ...]:
    if not isinstance(result, dict):
        raise InfrastructureError("WhisperX result must be a JSON object")

    raw_segments = result.get("segments")
    if not isinstance(raw_segments, list):
        raise InfrastructureError("WhisperX result must contain a segments list")

    segments: list[TranscriptSegment] = []
    for fallback_index, raw_segment in enumerate(raw_segments):
        if not isinstance(raw_segment, Mapping):
            raise InfrastructureError("WhisperX segment must be a JSON object")

        text = str(raw_segment.get("text", "")).strip()
        if not text:
            continue

        try:
            segments.append(
                TranscriptSegment(
                    index=_segment_index(raw_segment, fallback_index),
                    time_range=TimeRange(
                        start_seconds=_segment_float(raw_segment, "start"),
                        end_seconds=_segment_float(raw_segment, "end"),
                    ),
                    speaker_label=SpeakerLabel.anonymous(
                        _speaker_label(raw_segment, unknown_speaker_label),
                    ),
                    text=text,
                ),
            )
        except DomainValidationError as exc:
            raise InfrastructureError(
                f"invalid WhisperX segment at index {fallback_index}: {exc}",
            ) from exc

    return tuple(segments)


def _segment_index(segment: Mapping[str, Any], fallback_index: int) -> int:
    raw_index = segment.get("index", fallback_index)
    if not isinstance(raw_index, int) or raw_index < 0:
        raise InfrastructureError("WhisperX segment index must be non-negative")
    return raw_index


def _segment_float(segment: Mapping[str, Any], field: str) -> float:
    if field not in segment:
        raise InfrastructureError(f"WhisperX segment is missing {field}")

    try:
        value = float(segment[field])
    except (TypeError, ValueError) as exc:
        raise InfrastructureError(
            f"WhisperX segment {field} must be numeric",
        ) from exc

    if not math.isfinite(value):
        raise InfrastructureError(f"WhisperX segment {field} must be finite")

    return value


def _speaker_label(segment: Mapping[str, Any], unknown_speaker_label: str) -> str:
    raw_label = segment.get("speaker") or unknown_speaker_label
    label = str(raw_label).strip()
    if not label:
        raise InfrastructureError("WhisperX speaker label must not be empty")
    return label


__all__ = ["transcript_from_whisperx_result"]
