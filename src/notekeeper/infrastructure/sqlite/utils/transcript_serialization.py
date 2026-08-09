"""Transcript payload serialization."""

from typing import Any

from notekeeper.domain import (
    AudioTrackId,
    CampaignId,
    Transcript,
    TranscriptId,
    TranscriptSegment,
)

from .common_serialization import (
    speaker_label_from_dict,
    speaker_label_to_dict,
    time_range_from_dict,
    time_range_to_dict,
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
        campaign_id=CampaignId(campaign_id),
        audio_track_id=AudioTrackId(audio_track_id),
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


__all__ = ["transcript_from_payload", "transcript_to_payload"]
