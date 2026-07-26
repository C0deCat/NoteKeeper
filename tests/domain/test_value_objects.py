import math

import pytest

from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    CampaignId,
    DomainValidationError,
    ParticipantId,
    SpeakerLabel,
    SpeakerMapping,
    SpeakerMappingError,
    SpeakerMappingSource,
    SpeakerMappingStatus,
    TimeRange,
)


def test_time_range_accepts_valid_range() -> None:
    time_range = TimeRange(start_seconds=1, end_seconds=2.5)

    assert time_range.start_seconds == 1.0
    assert time_range.end_seconds == 2.5
    assert time_range.duration_seconds == 1.5


@pytest.mark.parametrize(
    ("start_seconds", "end_seconds"),
    [
        (-1, 1),
        (2, 1),
        (0, math.inf),
        (math.nan, 1),
    ],
)
def test_time_range_rejects_invalid_values(
    start_seconds: float,
    end_seconds: float,
) -> None:
    with pytest.raises(DomainValidationError):
        TimeRange(start_seconds=start_seconds, end_seconds=end_seconds)


def test_audio_metadata_requires_positive_duration() -> None:
    with pytest.raises(DomainValidationError):
        AudioMetadata(duration_seconds=0)


def test_audio_metadata_accepts_technical_fields() -> None:
    metadata = AudioMetadata(
        duration_seconds=12.5,
        sample_rate_hz=16000,
        channels=1,
        codec="pcm_s16le",
        format="wav",
        bitrate_bps=256000,
        file_size_bytes=4000,
        checksum="abc",
    )

    assert metadata.sample_rate_hz == 16000
    assert metadata.channels == 1
    assert metadata.codec == "pcm_s16le"


def test_artifact_ref_requires_non_empty_uri() -> None:
    with pytest.raises(DomainValidationError):
        ArtifactRef(uri=" ")


def test_speaker_label_factories_create_expected_kinds() -> None:
    anonymous = SpeakerLabel.anonymous("SPEAKER_00")
    named = SpeakerLabel.named("Alice")

    assert anonymous.value == "SPEAKER_00"
    assert named.value == "Alice"


def test_speaker_label_requires_non_empty_value() -> None:
    with pytest.raises(DomainValidationError):
        SpeakerLabel.named("")


def test_speaker_mapping_rejects_invalid_confidence() -> None:
    with pytest.raises(SpeakerMappingError):
        SpeakerMapping(
            anonymous_label=SpeakerLabel.anonymous("SPEAKER_00"),
            named_label=SpeakerLabel.named("Alice"),
            participant_id=ParticipantId("participant-1"),
            confidence=1.1,
            source=SpeakerMappingSource.AUTOMATIC,
            status=SpeakerMappingStatus.CONFIRMED,
        )


def test_confirmed_mapping_requires_named_label() -> None:
    with pytest.raises(SpeakerMappingError):
        SpeakerMapping(
            anonymous_label=SpeakerLabel.anonymous("SPEAKER_00"),
            named_label=None,
            participant_id=ParticipantId("participant-1"),
            confidence=0.9,
            source=SpeakerMappingSource.MANUAL,
            status=SpeakerMappingStatus.CONFIRMED,
        )


def test_confirmed_mapping_allows_standalone_named_label() -> None:
    mapping = SpeakerMapping(
        anonymous_label=SpeakerLabel.anonymous("SPEAKER_00"),
        named_label=SpeakerLabel.named("Random Guest"),
        participant_id=None,
        confidence=1.0,
        source=SpeakerMappingSource.MANUAL,
        status=SpeakerMappingStatus.CONFIRMED,
    )

    assert mapping.named_label == SpeakerLabel.named("Random Guest")
    assert mapping.participant_id is None


def test_domain_ids_are_plain_runtime_values() -> None:
    campaign_id = CampaignId("campaign-1")

    assert campaign_id == "campaign-1"
