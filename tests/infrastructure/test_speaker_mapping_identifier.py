from notekeeper.application import PreparedAudioResult, PreparedVoiceSampleRange
from notekeeper.domain import (
    ArtifactRef,
    AudioTrackId,
    Campaign,
    CampaignId,
    Participant,
    ParticipantId,
    SpeakerLabel,
    SpeakerMappingSource,
    SpeakerMappingStatus,
    TimeRange,
    Transcript,
    TranscriptId,
    TranscriptSegment,
    VoiceSampleId,
)
from notekeeper.infrastructure.speaker_mapping import SampleBasedSpeakerIdentifier


def test_sample_based_identifier_confirms_clean_sample_overlap() -> None:
    campaign = _campaign("Alice")
    prepared_audio = _prepared_audio(
        _sample_range("sample-1", "participant-1", 10, 12),
    )
    transcript = _transcript(
        _segment(0, 0, 1, "SPEAKER_01"),
        _segment(1, 10.25, 11.75, "SPEAKER_00"),
    )

    mappings = SampleBasedSpeakerIdentifier().identify(
        campaign,
        transcript,
        prepared_audio=prepared_audio,
    )

    assert len(mappings) == 1
    assert mappings[0].anonymous_label == SpeakerLabel.anonymous("SPEAKER_00")
    assert mappings[0].named_label == SpeakerLabel.named("Alice")
    assert mappings[0].participant_id == ParticipantId("participant-1")
    assert mappings[0].confidence == 1.0
    assert mappings[0].source is SpeakerMappingSource.SAMPLE_BASED
    assert mappings[0].status is SpeakerMappingStatus.CONFIRMED


def test_sample_based_identifier_marks_mixed_sample_labels_uncertain() -> None:
    campaign = _campaign("Alice")
    prepared_audio = _prepared_audio(
        _sample_range("sample-1", "participant-1", 10, 12),
    )
    transcript = _transcript(
        _segment(0, 10, 11, "SPEAKER_00"),
        _segment(1, 11, 12, "SPEAKER_01"),
    )

    mappings = SampleBasedSpeakerIdentifier().identify(
        campaign,
        transcript,
        prepared_audio=prepared_audio,
    )

    assert len(mappings) == 1
    assert mappings[0].confidence == 0.5
    assert mappings[0].status is SpeakerMappingStatus.UNCERTAIN


def test_sample_based_identifier_preserves_duplicate_label_candidates() -> None:
    campaign = _campaign("Alice", "Bob")
    prepared_audio = _prepared_audio(
        _sample_range("sample-1", "participant-1", 10, 11),
        _sample_range("sample-2", "participant-2", 12, 13),
    )
    transcript = _transcript(
        _segment(0, 10, 11, "SPEAKER_00"),
        _segment(1, 12, 13, "SPEAKER_00"),
    )

    mappings = SampleBasedSpeakerIdentifier().identify(
        campaign,
        transcript,
        prepared_audio=prepared_audio,
    )

    assert len(mappings) == 2
    assert {mapping.participant_id for mapping in mappings} == {
        ParticipantId("participant-1"),
        ParticipantId("participant-2"),
    }
    assert {mapping.anonymous_label for mapping in mappings} == {
        SpeakerLabel.anonymous("SPEAKER_00"),
    }
    assert all(
        mapping.status is SpeakerMappingStatus.CONFIRMED
        for mapping in mappings
    )


def test_sample_based_identifier_returns_no_mapping_without_sample_overlap() -> None:
    campaign = _campaign("Alice")
    prepared_audio = _prepared_audio(
        _sample_range("sample-1", "participant-1", 10, 11),
    )
    transcript = _transcript(_segment(0, 0, 1, "SPEAKER_00"))

    mappings = SampleBasedSpeakerIdentifier().identify(
        campaign,
        transcript,
        prepared_audio=prepared_audio,
    )

    assert mappings == ()


def _campaign(*names: str) -> Campaign:
    campaign_id = CampaignId("campaign-1")
    return Campaign(
        id=campaign_id,
        name="Campaign",
        participants=tuple(
            Participant(
                id=ParticipantId(f"participant-{index}"),
                campaign_id=campaign_id,
                display_name=name,
            )
            for index, name in enumerate(names, start=1)
        ),
    )


def _prepared_audio(
    *voice_sample_ranges: PreparedVoiceSampleRange,
) -> PreparedAudioResult:
    return PreparedAudioResult(
        audio_artifact=ArtifactRef(
            uri="campaign-1/records/transient/job-1/prepared.wav",
        ),
        manifest_artifact=ArtifactRef(
            uri="campaign-1/records/manifests/job-1/prepared-audio.json",
        ),
        source_audio_artifact=ArtifactRef(
            uri="campaign-1/records/normalized/audio-track-1.wav",
        ),
        session_time_range=TimeRange(0, 10),
        voice_sample_ranges=voice_sample_ranges,
    )


def _sample_range(
    voice_sample_id: str,
    participant_id: str,
    start: float,
    end: float,
) -> PreparedVoiceSampleRange:
    return PreparedVoiceSampleRange(
        source_artifact=ArtifactRef(uri=f"campaign-1/players/{voice_sample_id}.wav"),
        voice_sample_id=VoiceSampleId(voice_sample_id),
        participant_id=ParticipantId(participant_id),
        time_range=TimeRange(start, end),
    )


def _transcript(*segments: TranscriptSegment) -> Transcript:
    return Transcript(
        id=TranscriptId("transcript-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
        segments=segments,
    )


def _segment(
    index: int,
    start: float,
    end: float,
    speaker_label: str,
) -> TranscriptSegment:
    return TranscriptSegment(
        index=index,
        time_range=TimeRange(start, end),
        speaker_label=SpeakerLabel.anonymous(speaker_label),
        text="Sample speech",
    )
