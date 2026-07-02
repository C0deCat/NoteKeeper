"""Campaign aggregate lookup helpers."""

from notekeeper.application.errors import NotFoundError
from notekeeper.domain import (
    AudioTrack,
    AudioTrackId,
    Participant,
    ParticipantId,
    VoiceSample,
    VoiceSampleId,
)


def find_participant(
    participants: tuple[Participant, ...],
    participant_id: str,
) -> Participant:
    for participant in participants:
        if participant.id == ParticipantId(participant_id):
            return participant
    raise NotFoundError(f"participant {participant_id} was not found")


def find_voice_sample(
    voice_samples: tuple[VoiceSample, ...],
    voice_sample_id: str,
) -> VoiceSample:
    for voice_sample in voice_samples:
        if voice_sample.id == VoiceSampleId(voice_sample_id):
            return voice_sample
    raise NotFoundError(f"voice sample {voice_sample_id} was not found")


def find_audio_track(
    audio_tracks: tuple[AudioTrack, ...],
    audio_track_id: str,
) -> AudioTrack:
    for audio_track in audio_tracks:
        if audio_track.id == AudioTrackId(audio_track_id):
            return audio_track
    raise NotFoundError(f"audio track {audio_track_id} was not found")
