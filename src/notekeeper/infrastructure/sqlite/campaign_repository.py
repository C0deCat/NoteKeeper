"""SQLite campaign repository."""

from notekeeper.application import RepositoryScope
from notekeeper.application.ports import CampaignRepository
from notekeeper.application.errors import PortExecutionError
from notekeeper.domain import Campaign, CampaignId, WorkspaceId

from .database import SQLiteDatabase
from .scope import require_existing_resource_access, workspace_predicate
from .utils import (
    list_audio_tracks,
    list_participants,
    list_voice_samples,
    save_audio_track,
    save_participant,
    save_voice_sample,
)


class SQLiteCampaignRepository(CampaignRepository):
    def __init__(self, database: SQLiteDatabase, scope: RepositoryScope) -> None:
        self._database = database
        self._scope = scope

    def get(self, campaign_id: CampaignId) -> Campaign | None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                f"SELECT id, name, workspace_id FROM campaigns WHERE id = ? AND {predicate}",
                (str(campaign_id), *parameters),
            ).fetchone()
            if row is None:
                return None
            return Campaign(
                id=CampaignId(row["id"]),
                name=row["name"],
                workspace_id=WorkspaceId(row["workspace_id"]),
                participants=list_participants(connection, campaign_id),
                voice_samples=list_voice_samples(connection, campaign_id),
                audio_tracks=list_audio_tracks(connection, campaign_id),
            )

    def list(self) -> tuple[Campaign, ...]:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            rows = connection.execute(
                f"SELECT id FROM campaigns WHERE {predicate} ORDER BY rowid",
                parameters,
            ).fetchall()
        campaigns = [self.get(CampaignId(row["id"])) for row in rows]
        return tuple(campaign for campaign in campaigns if campaign is not None)

    def save(self, campaign: Campaign) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO campaigns (id, name, workspace_id)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name = excluded.name
                WHERE campaigns.workspace_id = excluded.workspace_id
                """,
                (str(campaign.id), campaign.name, str(campaign.workspace_id)),
            )
            predicate, parameters = workspace_predicate(self._scope)
            owner_row = connection.execute(
                f"SELECT workspace_id FROM campaigns WHERE id = ? AND {predicate}",
                (str(campaign.id), *parameters),
            ).fetchone()
            if owner_row is None or owner_row["workspace_id"] != str(
                campaign.workspace_id
            ):
                raise PortExecutionError("campaign workspace cannot be changed")
            for table, resources in (
                ("participants", campaign.participants),
                ("voice_samples", campaign.voice_samples),
                ("audio_tracks", campaign.audio_tracks),
            ):
                for resource in resources:
                    require_existing_resource_access(
                        connection,
                        self._scope,
                        table=table,
                        key_column="id",
                        key=str(resource.id),
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
            predicate, parameters = workspace_predicate(self._scope)
            visible = connection.execute(
                f"SELECT 1 FROM campaigns WHERE id = ? AND {predicate}",
                (str(campaign_id), *parameters),
            ).fetchone()
            if visible is None:
                return
            job_rows = connection.execute(
                "SELECT id FROM jobs WHERE campaign_id = ?",
                (str(campaign_id),),
            ).fetchall()
            transcript_rows = connection.execute(
                "SELECT id FROM transcripts WHERE campaign_id = ?",
                (str(campaign_id),),
            ).fetchall()
            for row in job_rows:
                connection.execute(
                    "DELETE FROM progress_event_snapshots WHERE operation_id = ?",
                    (row["id"],),
                )
                connection.execute(
                    "DELETE FROM speaker_review_submissions WHERE job_id = ?",
                    (row["id"],),
                )
                connection.execute(
                    "DELETE FROM speaker_mappings WHERE job_id = ?",
                    (row["id"],),
                )
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
