"""SQLite campaign repository."""

from notekeeper.domain import Campaign, CampaignId

from .database import SQLiteDatabase
from .utils import (
    list_audio_tracks,
    list_participants,
    list_voice_samples,
    save_audio_track,
    save_participant,
    save_voice_sample,
)


class SQLiteCampaignRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def get(self, campaign_id: CampaignId) -> Campaign | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT id, name FROM campaigns WHERE id = ?",
                (str(campaign_id),),
            ).fetchone()
            if row is None:
                return None
            return Campaign(
                id=CampaignId(row["id"]),
                name=row["name"],
                participants=list_participants(connection, campaign_id),
                voice_samples=list_voice_samples(connection, campaign_id),
                audio_tracks=list_audio_tracks(connection, campaign_id),
            )

    def list(self) -> tuple[Campaign, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT id FROM campaigns ORDER BY rowid",
            ).fetchall()
        campaigns = [self.get(CampaignId(row["id"])) for row in rows]
        return tuple(campaign for campaign in campaigns if campaign is not None)

    def save(self, campaign: Campaign) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO campaigns (id, name)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET name = excluded.name
                """,
                (str(campaign.id), campaign.name),
            )
            connection.execute(
                "DELETE FROM voice_samples WHERE campaign_id = ?",
                (str(campaign.id),),
            )
            connection.execute(
                "DELETE FROM participants WHERE campaign_id = ?",
                (str(campaign.id),),
            )
            connection.execute(
                "DELETE FROM audio_tracks WHERE campaign_id = ?",
                (str(campaign.id),),
            )
            for participant in campaign.participants:
                save_participant(connection, participant)
            for voice_sample in campaign.voice_samples:
                save_voice_sample(connection, voice_sample)
            for audio_track in campaign.audio_tracks:
                save_audio_track(connection, audio_track)

    def delete(self, campaign_id: CampaignId) -> None:
        with self._database.connect() as connection:
            transcript_rows = connection.execute(
                "SELECT id FROM transcripts WHERE campaign_id = ?",
                (str(campaign_id),),
            ).fetchall()
            for row in transcript_rows:
                connection.execute(
                    "DELETE FROM recaps WHERE transcript_id = ?",
                    (row["id"],),
                )
            for table in (
                "jobs",
                "transcripts",
                "audio_tracks",
                "voice_samples",
                "participants",
            ):
                connection.execute(
                    f"DELETE FROM {table} WHERE campaign_id = ?",
                    (str(campaign_id),),
                )
            connection.execute(
                "DELETE FROM campaigns WHERE id = ?",
                (str(campaign_id),),
            )
