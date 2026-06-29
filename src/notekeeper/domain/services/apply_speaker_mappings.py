"""Speaker mapping application service."""

from dataclasses import dataclass, replace

from ..models import Campaign, Transcript
from ..value_objects import PipelineWarning, SpeakerMapping
from ._speaker_mapping_helpers import unambiguous_confirmed_mappings
from .speaker_mapping_issues import find_speaker_mapping_issues


@dataclass(frozen=True, slots=True)
class SpeakerMappingApplicationResult:
    transcript: Transcript
    warnings: tuple[PipelineWarning, ...]
    applied_mappings: tuple[SpeakerMapping, ...]


def apply_speaker_mappings(
    campaign: Campaign,
    transcript: Transcript,
    mappings: tuple[SpeakerMapping, ...] | list[SpeakerMapping],
) -> SpeakerMappingApplicationResult:
    mappings = tuple(mappings)
    warnings = find_speaker_mapping_issues(campaign, transcript, mappings)
    participant_ids = {participant.id for participant in campaign.participants}
    mapping_by_label = unambiguous_confirmed_mappings(mappings, participant_ids)

    transformed_segments = []
    for segment in transcript.segments:
        replacement_label = mapping_by_label.get(segment.speaker_label)
        if replacement_label is None:
            transformed_segments.append(segment)
            continue

        transformed_segments.append(replace(segment, speaker_label=replacement_label))

    transformed = replace(transcript, segments=tuple(transformed_segments))
    applied = tuple(
        mapping
        for mapping in mappings
        if mapping.anonymous_label in mapping_by_label
        and mapping.named_label == mapping_by_label[mapping.anonymous_label]
    )

    return SpeakerMappingApplicationResult(
        transcript=transformed,
        warnings=warnings,
        applied_mappings=applied,
    )
