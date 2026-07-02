"""Serialization helpers for SQLite repositories."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from notekeeper.domain import (
    AudioMetadata,
    PipelineWarning,
    PipelineWarningKind,
    Recap,
    RecapChunk,
    RecapId,
    SpeakerLabel,
    SpeakerLabelKind,
    TimeRange,
    Transcript,
    TranscriptId,
    TranscriptSegment,
)


def metadata_to_dict(metadata: AudioMetadata) -> dict[str, Any]:
    return {
        "duration_seconds": metadata.duration_seconds,
        "sample_rate_hz": metadata.sample_rate_hz,
        "channels": metadata.channels,
        "codec": metadata.codec,
        "format": metadata.format,
        "bitrate_bps": metadata.bitrate_bps,
        "file_size_bytes": metadata.file_size_bytes,
        "checksum": metadata.checksum,
    }


def metadata_from_dict(payload: dict[str, Any]) -> AudioMetadata:
    return AudioMetadata(
        duration_seconds=payload["duration_seconds"],
        sample_rate_hz=payload.get("sample_rate_hz"),
        channels=payload.get("channels"),
        codec=payload.get("codec"),
        format=payload.get("format"),
        bitrate_bps=payload.get("bitrate_bps"),
        file_size_bytes=payload.get("file_size_bytes"),
        checksum=payload.get("checksum"),
    )


def transcript_to_payload(transcript: Transcript) -> dict[str, Any]:
    return {
        "segments": [
            {
                "index": segment.index,
                "time_range": time_range_to_dict(segment.time_range),
                "speaker_label": speaker_label_to_dict(segment.speaker_label),
                "text": segment.text,
            }
            for segment in transcript.segments
        ],
    }


def transcript_from_payload(
    *,
    transcript_id: str,
    campaign_id: str,
    audio_track_id: str,
    payload: dict[str, Any],
) -> Transcript:
    return Transcript(
        id=TranscriptId(transcript_id),
        campaign_id=campaign_id,
        audio_track_id=audio_track_id,
        segments=tuple(
            TranscriptSegment(
                index=segment["index"],
                time_range=time_range_from_dict(segment["time_range"]),
                speaker_label=speaker_label_from_dict(segment["speaker_label"]),
                text=segment["text"],
            )
            for segment in payload.get("segments", ())
        ),
    )


def recap_to_payload(recap: Recap) -> dict[str, Any]:
    return {
        "markdown": recap.markdown,
        "chunks": [
            {
                "markdown": chunk.markdown,
                "time_range": (
                    time_range_to_dict(chunk.time_range)
                    if chunk.time_range is not None
                    else None
                ),
                "source_segment_indexes": list(chunk.source_segment_indexes),
            }
            for chunk in recap.chunks
        ],
    }


def recap_from_payload(
    *,
    recap_id: str,
    transcript_id: str,
    payload: dict[str, Any],
) -> Recap:
    return Recap(
        id=RecapId(recap_id),
        transcript_id=TranscriptId(transcript_id),
        markdown=payload["markdown"],
        chunks=tuple(
            RecapChunk(
                markdown=chunk["markdown"],
                time_range=(
                    time_range_from_dict(chunk["time_range"])
                    if chunk.get("time_range") is not None
                    else None
                ),
                source_segment_indexes=tuple(chunk.get("source_segment_indexes", ())),
            )
            for chunk in payload.get("chunks", ())
        ),
    )


def warning_to_dict(warning: PipelineWarning) -> dict[str, Any]:
    return {
        "kind": warning.kind.value,
        "message": warning.message,
        "time_range": (
            time_range_to_dict(warning.time_range)
            if warning.time_range is not None
            else None
        ),
        "speaker_label": (
            speaker_label_to_dict(warning.speaker_label)
            if warning.speaker_label is not None
            else None
        ),
        "participant_id": (
            str(warning.participant_id)
            if warning.participant_id is not None
            else None
        ),
    }


def warning_from_dict(payload: dict[str, Any]) -> PipelineWarning:
    return PipelineWarning(
        kind=PipelineWarningKind(payload["kind"]),
        message=payload["message"],
        time_range=(
            time_range_from_dict(payload["time_range"])
            if payload.get("time_range") is not None
            else None
        ),
        speaker_label=(
            speaker_label_from_dict(payload["speaker_label"])
            if payload.get("speaker_label") is not None
            else None
        ),
        participant_id=payload.get("participant_id"),
    )


def time_range_to_dict(time_range: TimeRange) -> dict[str, float]:
    return {
        "start_seconds": time_range.start_seconds,
        "end_seconds": time_range.end_seconds,
    }


def time_range_from_dict(payload: dict[str, Any]) -> TimeRange:
    return TimeRange(
        start_seconds=payload["start_seconds"],
        end_seconds=payload["end_seconds"],
    )


def speaker_label_to_dict(label: SpeakerLabel) -> dict[str, str]:
    return {"value": label.value, "kind": label.kind.value}


def speaker_label_from_dict(payload: dict[str, Any]) -> SpeakerLabel:
    return SpeakerLabel(
        value=payload["value"],
        kind=SpeakerLabelKind(payload["kind"]),
    )


def datetime_to_text(value: datetime) -> str:
    return value.isoformat()


def datetime_from_text(value: str) -> datetime:
    return datetime.fromisoformat(value)
