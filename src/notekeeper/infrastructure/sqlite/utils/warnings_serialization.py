"""Pipeline warning payload serialization."""

from typing import Any

from notekeeper.domain import ParticipantId, PipelineWarning, PipelineWarningKind

from .common_serialization import (
    speaker_label_from_dict,
    speaker_label_to_dict,
    time_range_from_dict,
    time_range_to_dict,
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
            str(warning.participant_id) if warning.participant_id is not None else None
        ),
    }


def warning_from_dict(payload: dict[str, Any]) -> PipelineWarning:
    participant_id = payload.get("participant_id")
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
        participant_id=(
            ParticipantId(str(participant_id)) if participant_id is not None else None
        ),
    )


__all__ = ["warning_from_dict", "warning_to_dict"]
