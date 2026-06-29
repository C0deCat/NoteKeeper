import pytest

from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    Campaign,
    CampaignId,
    CampaignValidationError,
    Participant,
    ParticipantId,
    VoiceSample,
    VoiceSampleId,
    add_participant,
    add_voice_sample,
    ensure_campaign_ready_for_processing,
)


def make_campaign() -> Campaign:
    return Campaign(id=CampaignId("campaign-1"), name="Storm King's Thunder")


def make_participant(
    participant_id: str = "participant-1",
    name: str = "Alice",
    campaign_id: CampaignId = CampaignId("campaign-1"),
) -> Participant:
    return Participant(
        id=ParticipantId(participant_id),
        campaign_id=campaign_id,
        display_name=name,
    )


def make_voice_sample(
    participant_id: ParticipantId = ParticipantId("participant-1"),
    campaign_id: CampaignId = CampaignId("campaign-1"),
) -> VoiceSample:
    return VoiceSample(
        id=VoiceSampleId("sample-1"),
        campaign_id=campaign_id,
        participant_id=participant_id,
        artifact=ArtifactRef(uri="samples/alice.wav"),
        metadata=AudioMetadata(duration_seconds=12),
    )


def test_add_participant_returns_campaign_with_new_participant() -> None:
    campaign = make_campaign()
    participant = make_participant()

    updated = add_participant(campaign, participant)

    assert updated is not campaign
    assert updated.participants == (participant,)


def test_add_participant_rejects_duplicate_id() -> None:
    campaign = add_participant(make_campaign(), make_participant())

    with pytest.raises(CampaignValidationError):
        add_participant(campaign, make_participant(name="Bob"))


def test_add_participant_rejects_duplicate_display_name_case_insensitive() -> None:
    campaign = add_participant(make_campaign(), make_participant(name="Alice"))

    with pytest.raises(CampaignValidationError):
        add_participant(campaign, make_participant("participant-2", "alice"))


def test_add_participant_rejects_wrong_campaign() -> None:
    campaign = make_campaign()
    participant = make_participant(campaign_id=CampaignId("other-campaign"))

    with pytest.raises(CampaignValidationError):
        add_participant(campaign, participant)


def test_add_voice_sample_returns_campaign_with_sample() -> None:
    participant = make_participant()
    campaign = add_participant(make_campaign(), participant)
    sample = make_voice_sample(participant_id=participant.id)

    updated = add_voice_sample(campaign, sample)

    assert updated.voice_samples == (sample,)


def test_add_voice_sample_rejects_unknown_participant() -> None:
    campaign = add_participant(make_campaign(), make_participant())
    sample = make_voice_sample(participant_id=ParticipantId("missing"))

    with pytest.raises(CampaignValidationError):
        add_voice_sample(campaign, sample)


def test_add_voice_sample_rejects_wrong_campaign() -> None:
    participant = make_participant()
    campaign = add_participant(make_campaign(), participant)
    sample = make_voice_sample(campaign_id=CampaignId("other-campaign"))

    with pytest.raises(CampaignValidationError):
        add_voice_sample(campaign, sample)


def test_campaign_ready_requires_participant_and_voice_samples() -> None:
    with pytest.raises(CampaignValidationError):
        ensure_campaign_ready_for_processing(make_campaign())

    participant = make_participant()
    campaign = add_participant(make_campaign(), participant)
    with pytest.raises(CampaignValidationError):
        ensure_campaign_ready_for_processing(campaign)

    ready_campaign = add_voice_sample(
        campaign,
        make_voice_sample(participant_id=participant.id),
    )
    ensure_campaign_ready_for_processing(ready_campaign)
