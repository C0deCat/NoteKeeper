import notekeeper.domain as domain
import notekeeper.domain.models as models
import notekeeper.domain.services as services
import notekeeper.domain.value_objects as value_objects


def test_domain_reexports_public_api() -> None:
    assert domain.Campaign is models.Campaign
    assert domain.Participant is models.Participant
    assert domain.TimeRange is value_objects.TimeRange
    assert domain.SpeakerMapping is value_objects.SpeakerMapping
    assert domain.add_participant is services.add_participant
    assert domain.apply_speaker_mappings is services.apply_speaker_mappings


def test_package_facades_reexport_expected_names() -> None:
    assert models.TranscriptSegment.__name__ == "TranscriptSegment"
    assert value_objects.AudioMetadata.__name__ == "AudioMetadata"
    assert services.SpeakerMappingApplicationResult.__name__ == (
        "SpeakerMappingApplicationResult"
    )
