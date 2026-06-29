"""Shared speaker mapping service helpers."""

from ..enums import SpeakerMappingStatus
from ..ids import ParticipantId
from ..value_objects import SpeakerLabel, SpeakerMapping


def unambiguous_confirmed_mappings(
    mappings: tuple[SpeakerMapping, ...],
    participant_ids: set[ParticipantId],
) -> dict[SpeakerLabel, SpeakerLabel]:
    confirmed_by_label: dict[SpeakerLabel, list[SpeakerMapping]] = {}

    for mapping in mappings:
        if mapping.status is not SpeakerMappingStatus.CONFIRMED:
            continue
        if mapping.participant_id not in participant_ids:
            continue
        if mapping.named_label is None:
            continue

        confirmed_by_label.setdefault(mapping.anonymous_label, []).append(mapping)

    result: dict[SpeakerLabel, SpeakerLabel] = {}
    for anonymous_label, label_mappings in confirmed_by_label.items():
        named_labels = {mapping.named_label for mapping in label_mappings}
        participant_ids_for_label = {mapping.participant_id for mapping in label_mappings}
        if (
            len(label_mappings) == 1
            and len(named_labels) == 1
            and len(participant_ids_for_label) == 1
        ):
            result[anonymous_label] = label_mappings[0].named_label

    return result
