"""Sample-based speaker identification adapter."""

from __future__ import annotations

from collections import defaultdict

from notekeeper.application.ports import SpeakerIdentifier
from notekeeper.application.results import PreparedAudioResult
from notekeeper.domain import (
    Campaign,
    ParticipantId,
    SpeakerLabel,
    SpeakerLabelKind,
    SpeakerMapping,
    SpeakerMappingSource,
    SpeakerMappingStatus,
    TimeRange,
    Transcript,
)
from notekeeper.infrastructure.errors import InfrastructureError


class SampleBasedSpeakerIdentifier(SpeakerIdentifier):
    def __init__(
        self,
        *,
        min_overlap_seconds: float = 0.25,
        min_dominance_ratio: float = 0.8,
    ) -> None:
        if min_overlap_seconds < 0:
            raise InfrastructureError("min_overlap_seconds must be non-negative")
        if min_dominance_ratio <= 0 or min_dominance_ratio > 1:
            raise InfrastructureError("min_dominance_ratio must be between 0 and 1")

        self._min_overlap_seconds = min_overlap_seconds
        self._min_dominance_ratio = min_dominance_ratio

    def identify(
        self,
        campaign: Campaign,
        transcript: Transcript,
        *,
        prepared_audio: PreparedAudioResult,
    ) -> tuple[SpeakerMapping, ...]:
        participants = {
            participant.id: participant
            for participant in campaign.participants
        }
        overlap_by_participant: dict[
            ParticipantId,
            dict[SpeakerLabel, float],
        ] = defaultdict(lambda: defaultdict(float))

        for sample_range in prepared_audio.voice_sample_ranges:
            participant = participants.get(sample_range.participant_id)
            if participant is None:
                continue

            label_overlap = overlap_by_participant[participant.id]
            for segment in transcript.segments:
                if segment.speaker_label.kind is not SpeakerLabelKind.ANONYMOUS:
                    continue

                overlap_seconds = _overlap_seconds(
                    sample_range.time_range,
                    segment.time_range,
                )
                if overlap_seconds > 0:
                    label_overlap[segment.speaker_label] += overlap_seconds

        mappings: list[SpeakerMapping] = []
        for participant_id, labels in overlap_by_participant.items():
            participant = participants.get(participant_id)
            if participant is None or not labels:
                continue

            top_label, top_overlap = max(
                labels.items(),
                key=lambda item: (item[1], item[0].value),
            )
            total_overlap = sum(labels.values())
            confidence = top_overlap / total_overlap if total_overlap > 0 else None
            status = SpeakerMappingStatus.UNCERTAIN
            if (
                confidence is not None
                and top_overlap >= self._min_overlap_seconds
                and confidence >= self._min_dominance_ratio
            ):
                status = SpeakerMappingStatus.CONFIRMED

            mappings.append(
                SpeakerMapping(
                    anonymous_label=top_label,
                    named_label=SpeakerLabel.named(participant.display_name),
                    participant_id=participant.id,
                    confidence=confidence,
                    source=SpeakerMappingSource.SAMPLE_BASED,
                    status=status,
                ),
            )

        return tuple(mappings)


def _overlap_seconds(left: TimeRange, right: TimeRange) -> float:
    start = max(left.start_seconds, right.start_seconds)
    end = min(left.end_seconds, right.end_seconds)
    return max(0.0, end - start)
