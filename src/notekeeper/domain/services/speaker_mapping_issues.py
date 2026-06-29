"""Speaker mapping issue detection service."""

from ..enums import PipelineWarningKind, SpeakerLabelKind, SpeakerMappingStatus
from ..ids import ParticipantId
from ..models import Campaign, Transcript
from ..value_objects import PipelineWarning, SpeakerLabel, SpeakerMapping
from ._speaker_mapping_helpers import unambiguous_confirmed_mappings
from .transcript_validation import validate_transcript


def find_speaker_mapping_issues(
    campaign: Campaign,
    transcript: Transcript,
    mappings: tuple[SpeakerMapping, ...] | list[SpeakerMapping],
) -> tuple[PipelineWarning, ...]:
    validate_transcript(transcript)

    mappings = tuple(mappings)
    warnings: list[PipelineWarning] = []
    participant_ids = {participant.id for participant in campaign.participants}

    _collect_mapping_state_warnings(warnings, participant_ids, mappings)
    _collect_duplicate_and_conflict_warnings(warnings, participant_ids, mappings)
    _collect_unresolved_label_warnings(warnings, transcript, participant_ids, mappings)

    return tuple(warnings)


def _collect_mapping_state_warnings(
    warnings: list[PipelineWarning],
    participant_ids: set[ParticipantId],
    mappings: tuple[SpeakerMapping, ...],
) -> None:
    for mapping in mappings:
        if (
            mapping.participant_id is not None
            and mapping.participant_id not in participant_ids
        ):
            warnings.append(
                PipelineWarning(
                    kind=PipelineWarningKind.UNKNOWN_PARTICIPANT,
                    message=(
                        f"mapping for {mapping.anonymous_label.value} references "
                        "an unknown participant"
                    ),
                    speaker_label=mapping.anonymous_label,
                    participant_id=mapping.participant_id,
                )
            )

        if mapping.status is SpeakerMappingStatus.UNCERTAIN:
            warnings.append(
                PipelineWarning(
                    kind=PipelineWarningKind.UNCERTAIN_MAPPING,
                    message=f"mapping for {mapping.anonymous_label.value} is uncertain",
                    speaker_label=mapping.anonymous_label,
                    participant_id=mapping.participant_id,
                )
            )


def _collect_duplicate_and_conflict_warnings(
    warnings: list[PipelineWarning],
    participant_ids: set[ParticipantId],
    mappings: tuple[SpeakerMapping, ...],
) -> None:
    by_label: dict[SpeakerLabel, list[SpeakerMapping]] = {}
    for mapping in mappings:
        by_label.setdefault(mapping.anonymous_label, []).append(mapping)

    for anonymous_label, label_mappings in by_label.items():
        if len(label_mappings) > 1:
            warnings.append(
                PipelineWarning(
                    kind=PipelineWarningKind.DUPLICATE_MAPPING,
                    message=f"{anonymous_label.value} has multiple speaker mappings",
                    speaker_label=anonymous_label,
                )
            )

        confirmed_participants = {
            mapping.participant_id
            for mapping in label_mappings
            if mapping.status is SpeakerMappingStatus.CONFIRMED
            and mapping.participant_id in participant_ids
        }
        if len(confirmed_participants) > 1:
            warnings.append(
                PipelineWarning(
                    kind=PipelineWarningKind.CONFLICTING_MAPPING,
                    message=(
                        f"{anonymous_label.value} is mapped to multiple participants"
                    ),
                    speaker_label=anonymous_label,
                )
            )


def _collect_unresolved_label_warnings(
    warnings: list[PipelineWarning],
    transcript: Transcript,
    participant_ids: set[ParticipantId],
    mappings: tuple[SpeakerMapping, ...],
) -> None:
    anonymous_labels = {
        segment.speaker_label
        for segment in transcript.segments
        if segment.speaker_label.kind is SpeakerLabelKind.ANONYMOUS
    }
    unambiguous_mappings = unambiguous_confirmed_mappings(mappings, participant_ids)

    for anonymous_label in sorted(anonymous_labels, key=lambda label: label.value):
        if anonymous_label not in unambiguous_mappings:
            warnings.append(
                PipelineWarning(
                    kind=PipelineWarningKind.UNRESOLVED_SPEAKER_LABEL,
                    message=f"{anonymous_label.value} has no confirmed speaker mapping",
                    speaker_label=anonymous_label,
                )
            )
