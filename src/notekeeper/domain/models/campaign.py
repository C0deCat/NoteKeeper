"""Campaign entity."""

from dataclasses import dataclass

from ..errors import CampaignValidationError
from ..ids import AudioTrackId, CampaignId, ParticipantId, VoiceSampleId
from ..validation import as_tuple, non_empty_str
from .audio_track import AudioTrack
from .participant import Participant
from .voice_sample import VoiceSample


@dataclass(frozen=True, slots=True)
class Campaign:
    id: CampaignId
    name: str
    participants: tuple[Participant, ...] = ()
    voice_samples: tuple[VoiceSample, ...] = ()
    audio_tracks: tuple[AudioTrack, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", non_empty_str(self.name, "name"))
        object.__setattr__(
            self,
            "participants",
            as_tuple(self.participants, "participants"),
        )
        object.__setattr__(
            self,
            "voice_samples",
            as_tuple(self.voice_samples, "voice_samples"),
        )
        object.__setattr__(
            self,
            "audio_tracks",
            as_tuple(self.audio_tracks, "audio_tracks"),
        )

        self._validate_members()

    def _validate_members(self) -> None:
        participant_ids: set[ParticipantId] = set()
        participant_names: set[str] = set()

        for participant in self.participants:
            if participant.campaign_id != self.id:
                raise CampaignValidationError("participant belongs to another campaign")
            if participant.id in participant_ids:
                raise CampaignValidationError("campaign has duplicate participant ids")

            name_key = participant.display_name.casefold()
            if name_key in participant_names:
                raise CampaignValidationError("campaign has duplicate participant names")

            participant_ids.add(participant.id)
            participant_names.add(name_key)

        sample_ids: set[VoiceSampleId] = set()
        for voice_sample in self.voice_samples:
            if voice_sample.campaign_id != self.id:
                raise CampaignValidationError("voice sample belongs to another campaign")
            if voice_sample.participant_id not in participant_ids:
                raise CampaignValidationError(
                    "voice sample participant is not in the campaign"
                )
            if voice_sample.id in sample_ids:
                raise CampaignValidationError("campaign has duplicate voice sample ids")
            sample_ids.add(voice_sample.id)

        audio_track_ids: set[AudioTrackId] = set()
        for audio_track in self.audio_tracks:
            if audio_track.campaign_id != self.id:
                raise CampaignValidationError("audio track belongs to another campaign")
            if audio_track.id in audio_track_ids:
                raise CampaignValidationError("campaign has duplicate audio track ids")
            audio_track_ids.add(audio_track.id)
