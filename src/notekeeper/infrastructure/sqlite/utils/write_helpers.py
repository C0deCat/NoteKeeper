"""SQLite domain write helpers."""

import json

from notekeeper.domain import AudioTrack, Participant, VoiceSample

from .serialization import datetime_to_text, metadata_to_dict


def save_participant(connection, participant: Participant) -> None:
    connection.execute(
        """
        INSERT INTO participants (id, campaign_id, display_name)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            campaign_id = excluded.campaign_id,
            display_name = excluded.display_name
        """,
        (str(participant.id), str(participant.campaign_id), participant.display_name),
    )


def save_voice_sample(connection, voice_sample: VoiceSample) -> None:
    connection.execute(
        """
        INSERT INTO voice_samples (
            id,
            campaign_id,
            participant_id,
            artifact_uri,
            artifact_kind,
            artifact_checksum,
            metadata_json,
            recorded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            campaign_id = excluded.campaign_id,
            participant_id = excluded.participant_id,
            artifact_uri = excluded.artifact_uri,
            artifact_kind = excluded.artifact_kind,
            artifact_checksum = excluded.artifact_checksum,
            metadata_json = excluded.metadata_json,
            recorded_at = excluded.recorded_at
        """,
        (
            str(voice_sample.id),
            str(voice_sample.campaign_id),
            str(voice_sample.participant_id),
            voice_sample.artifact.uri,
            voice_sample.artifact.kind,
            voice_sample.artifact.checksum,
            json.dumps(metadata_to_dict(voice_sample.metadata)),
            (
                datetime_to_text(voice_sample.recorded_at)
                if voice_sample.recorded_at is not None
                else None
            ),
        ),
    )


def save_audio_track(connection, audio_track: AudioTrack) -> None:
    connection.execute(
        """
        INSERT INTO audio_tracks (
            id,
            campaign_id,
            artifact_uri,
            artifact_kind,
            artifact_checksum,
            metadata_json,
            title
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            campaign_id = excluded.campaign_id,
            artifact_uri = excluded.artifact_uri,
            artifact_kind = excluded.artifact_kind,
            artifact_checksum = excluded.artifact_checksum,
            metadata_json = excluded.metadata_json,
            title = excluded.title
        """,
        (
            str(audio_track.id),
            str(audio_track.campaign_id),
            audio_track.artifact.uri,
            audio_track.artifact.kind,
            audio_track.artifact.checksum,
            json.dumps(metadata_to_dict(audio_track.metadata)),
            audio_track.title,
        ),
    )
