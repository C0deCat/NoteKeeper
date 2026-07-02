"""SQLite aggregate list helpers."""

from notekeeper.domain import AudioTrack, CampaignId, Participant, VoiceSample

from .row_mappers import (
    audio_track_from_row,
    participant_from_row,
    voice_sample_from_row,
)


def list_participants(connection, campaign_id: CampaignId) -> tuple[Participant, ...]:
    rows = connection.execute(
        """
        SELECT id, campaign_id, display_name
        FROM participants
        WHERE campaign_id = ?
        ORDER BY rowid
        """,
        (str(campaign_id),),
    ).fetchall()
    return tuple(participant_from_row(row) for row in rows)


def list_voice_samples(connection, campaign_id: CampaignId) -> tuple[VoiceSample, ...]:
    rows = connection.execute(
        """
        SELECT * FROM voice_samples
        WHERE campaign_id = ?
        ORDER BY rowid
        """,
        (str(campaign_id),),
    ).fetchall()
    return tuple(voice_sample_from_row(row) for row in rows)


def list_audio_tracks(connection, campaign_id: CampaignId) -> tuple[AudioTrack, ...]:
    rows = connection.execute(
        """
        SELECT * FROM audio_tracks
        WHERE campaign_id = ?
        ORDER BY rowid
        """,
        (str(campaign_id),),
    ).fetchall()
    return tuple(audio_track_from_row(row) for row in rows)
