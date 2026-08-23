"""SQLite audio track repository."""

from notekeeper.application import RepositoryScope
from notekeeper.application.ports import AudioTrackRepository
from notekeeper.domain import AudioTrack, AudioTrackId, CampaignId
from notekeeper.infrastructure.errors import InfrastructureError

from .database import SQLiteDatabase
from .scope import (
    require_campaign_access,
    require_existing_resource_access,
    workspace_predicate,
)
from .utils import audio_track_from_row, list_audio_tracks, save_audio_track


class SQLiteAudioTrackRepository(AudioTrackRepository):
    def __init__(self, database: SQLiteDatabase, scope: RepositoryScope) -> None:
        self._database = database
        self._scope = scope

    def get(self, audio_track_id: AudioTrackId) -> AudioTrack | None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                f"""
                SELECT audio_tracks.* FROM audio_tracks
                LEFT JOIN campaigns ON campaigns.id = audio_tracks.campaign_id
                WHERE audio_tracks.id = ? AND {predicate}
                """,
                (str(audio_track_id), *parameters),
            ).fetchone()
        return audio_track_from_row(row) if row is not None else None

    def get_by_artifact_uri(
        self,
        campaign_id: CampaignId,
        artifact_uri: str,
    ) -> AudioTrack | None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                f"""
                SELECT audio_tracks.* FROM audio_tracks
                LEFT JOIN campaigns ON campaigns.id = audio_tracks.campaign_id
                WHERE audio_tracks.campaign_id = ? AND artifact_uri = ?
                  AND {predicate}
                """,
                (str(campaign_id), artifact_uri, *parameters),
            ).fetchone()
        return audio_track_from_row(row) if row is not None else None

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[AudioTrack, ...]:
        with self._database.connect() as connection:
            try:
                require_campaign_access(connection, campaign_id, self._scope)
            except InfrastructureError:
                return ()
            return list_audio_tracks(connection, campaign_id)

    def save(self, audio_track: AudioTrack) -> None:
        with self._database.connect() as connection:
            require_campaign_access(connection, audio_track.campaign_id, self._scope)
            require_existing_resource_access(
                connection,
                self._scope,
                table="audio_tracks",
                key_column="id",
                key=str(audio_track.id),
            )
            save_audio_track(connection, audio_track)

    def delete(self, audio_track_id: AudioTrackId) -> None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            connection.execute(
                f"""
                DELETE FROM audio_tracks WHERE id = ? AND campaign_id IN (
                    SELECT id FROM campaigns WHERE {predicate}
                )
                """,
                (str(audio_track_id), *parameters),
            )
