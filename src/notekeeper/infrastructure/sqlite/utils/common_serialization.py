"""Serialization for shared domain value objects."""

from datetime import datetime
from typing import Any

from notekeeper.domain import SpeakerLabel, SpeakerLabelKind, TimeRange


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


__all__ = [
    "datetime_from_text",
    "datetime_to_text",
    "speaker_label_from_dict",
    "speaker_label_to_dict",
    "time_range_from_dict",
    "time_range_to_dict",
]

