import pytest

from notekeeper.domain import (
    AudioTrackId,
    Campaign,
    CampaignId,
    Participant,
    ParticipantId,
    PipelineWarningKind,
    DomainValidationError,
    SpeakerLabel,
    SpeakerMapping,
    SpeakerMappingSource,
    SpeakerMappingStatus,
    TimeRange,
    Transcript,
    TranscriptId,
    TranscriptSegment,
    TranscriptValidationError,
    add_participant,
    apply_speaker_mappings,
    find_speaker_mapping_issues,
    validate_transcript,
)


def make_campaign() -> Campaign:
    campaign = Campaign(id=CampaignId("campaign-1"), name="Curse of Strahd")
    campaign = add_participant(
        campaign,
        Participant(
            id=ParticipantId("participant-1"),
            campaign_id=campaign.id,
            display_name="Alice",
        ),
    )
    return add_participant(
        campaign,
        Participant(
            id=ParticipantId("participant-2"),
            campaign_id=campaign.id,
            display_name="Bob",
        ),
    )


def make_transcript(*segments: TranscriptSegment) -> Transcript:
    return Transcript(
        id=TranscriptId("transcript-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("track-1"),
        segments=segments,
    )


def make_segment(
    index: int,
    start: float,
    end: float,
    speaker: SpeakerLabel,
    text: str = "Hello",
) -> TranscriptSegment:
    return TranscriptSegment(
        index=index,
        time_range=TimeRange(start, end),
        speaker_label=speaker,
        text=text,
    )


def confirmed_mapping(
    anonymous: str,
    named: str,
    participant_id: str,
) -> SpeakerMapping:
    return SpeakerMapping(
        anonymous_label=SpeakerLabel.anonymous(anonymous),
        named_label=SpeakerLabel.named(named),
        participant_id=ParticipantId(participant_id),
        confidence=0.95,
        source=SpeakerMappingSource.MANUAL,
        status=SpeakerMappingStatus.CONFIRMED,
    )


def test_validate_transcript_accepts_ordered_segments() -> None:
    transcript = make_transcript(
        make_segment(0, 0, 1, SpeakerLabel.anonymous("SPEAKER_00")),
        make_segment(1, 1, 2, SpeakerLabel.anonymous("SPEAKER_01")),
    )

    validate_transcript(transcript)


def test_transcript_segment_rejects_empty_text() -> None:
    with pytest.raises(DomainValidationError):
        make_segment(0, 0, 1, SpeakerLabel.anonymous("SPEAKER_00"), text=" ")


def test_validate_transcript_rejects_overlapping_segments() -> None:
    transcript = make_transcript(
        make_segment(0, 0, 2, SpeakerLabel.anonymous("SPEAKER_00")),
        make_segment(1, 1, 3, SpeakerLabel.anonymous("SPEAKER_01")),
    )

    with pytest.raises(TranscriptValidationError):
        validate_transcript(transcript)


def test_validate_transcript_rejects_non_increasing_indexes() -> None:
    transcript = make_transcript(
        make_segment(1, 0, 1, SpeakerLabel.anonymous("SPEAKER_00")),
        make_segment(1, 1, 2, SpeakerLabel.anonymous("SPEAKER_01")),
    )

    with pytest.raises(TranscriptValidationError):
        validate_transcript(transcript)


def test_apply_speaker_mappings_replaces_confirmed_labels() -> None:
    campaign = make_campaign()
    transcript = make_transcript(
        make_segment(0, 0, 1, SpeakerLabel.anonymous("SPEAKER_00")),
        make_segment(1, 1, 2, SpeakerLabel.anonymous("SPEAKER_01")),
    )
    mappings = (
        confirmed_mapping("SPEAKER_00", "Alice", "participant-1"),
        confirmed_mapping("SPEAKER_01", "Bob", "participant-2"),
    )

    result = apply_speaker_mappings(campaign, transcript, mappings)

    assert [segment.speaker_label.value for segment in result.transcript.segments] == [
        "Alice",
        "Bob",
    ]
    assert not result.warnings


def test_apply_speaker_mappings_leaves_unresolved_labels_intact() -> None:
    campaign = make_campaign()
    transcript = make_transcript(
        make_segment(0, 0, 1, SpeakerLabel.anonymous("SPEAKER_00")),
        make_segment(1, 1, 2, SpeakerLabel.anonymous("SPEAKER_01")),
    )

    result = apply_speaker_mappings(
        campaign,
        transcript,
        (confirmed_mapping("SPEAKER_00", "Alice", "participant-1"),),
    )

    assert result.transcript.segments[0].speaker_label.value == "Alice"
    assert result.transcript.segments[1].speaker_label.value == "SPEAKER_01"
    assert PipelineWarningKind.UNRESOLVED_SPEAKER_LABEL in {
        warning.kind for warning in result.warnings
    }


def test_find_speaker_mapping_issues_reports_uncertain_and_unknown() -> None:
    campaign = make_campaign()
    transcript = make_transcript(
        make_segment(0, 0, 1, SpeakerLabel.anonymous("SPEAKER_00")),
    )
    mappings = (
        SpeakerMapping(
            anonymous_label=SpeakerLabel.anonymous("SPEAKER_00"),
            named_label=SpeakerLabel.named("Alice"),
            participant_id=ParticipantId("participant-1"),
            confidence=0.4,
            source=SpeakerMappingSource.AUTOMATIC,
            status=SpeakerMappingStatus.UNCERTAIN,
        ),
        SpeakerMapping(
            anonymous_label=SpeakerLabel.anonymous("SPEAKER_01"),
            named_label=SpeakerLabel.named("Mallory"),
            participant_id=ParticipantId("unknown"),
            confidence=0.9,
            source=SpeakerMappingSource.MANUAL,
            status=SpeakerMappingStatus.CONFIRMED,
        ),
    )

    warnings = find_speaker_mapping_issues(campaign, transcript, mappings)

    assert PipelineWarningKind.UNCERTAIN_MAPPING in {warning.kind for warning in warnings}
    assert PipelineWarningKind.UNKNOWN_PARTICIPANT in {warning.kind for warning in warnings}


def test_find_speaker_mapping_issues_reports_duplicate_and_conflict() -> None:
    campaign = make_campaign()
    transcript = make_transcript(
        make_segment(0, 0, 1, SpeakerLabel.anonymous("SPEAKER_00")),
    )
    mappings = (
        confirmed_mapping("SPEAKER_00", "Alice", "participant-1"),
        confirmed_mapping("SPEAKER_00", "Bob", "participant-2"),
    )

    warnings = find_speaker_mapping_issues(campaign, transcript, mappings)
    warning_kinds = {warning.kind for warning in warnings}

    assert PipelineWarningKind.DUPLICATE_MAPPING in warning_kinds
    assert PipelineWarningKind.CONFLICTING_MAPPING in warning_kinds
