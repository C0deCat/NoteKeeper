"""SQLite audio track repository."""

from notekeeper.application.ports import AudioTrackRepository
from notekeeper.domain import AudioTrack, AudioTrackId, CampaignId

from .database import SQLiteDatabase
from .utils import audio_track_from_row, list_audio_tracks, save_audio_track


class SQLiteAudioTrackRepository(AudioTrackRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def get(self, audio_track_id: AudioTrackId) -> AudioTrack | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM audio_tracks WHERE id = ?",
                (str(audio_track_id),),
            ).fetchone()
        return audio_track_from_row(row) if row is not None else None

    def get_by_artifact_uri(
        self,
        campaign_id: CampaignId,
        artifact_uri: str,
    ) -> AudioTrack | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM audio_tracks
                WHERE campaign_id = ? AND artifact_uri = ?
                """,
                (str(campaign_id), artifact_uri),
            ).fetchone()
        return audio_track_from_row(row) if row is not None else None

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[AudioTrack, ...]:
        with self._database.connect() as connection:
            return list_audio_tracks(connection, campaign_id)

    def save(self, audio_track: AudioTrack) -> None:
        with self._database.connect() as connection:
            save_audio_track(connection, audio_track)

    def delete(self, audio_track_id: AudioTrackId) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM audio_tracks WHERE id = ?",
                (str(audio_track_id),),
            )
