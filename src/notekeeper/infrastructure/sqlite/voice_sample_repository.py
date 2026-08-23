"""SQLite voice sample repository."""

from notekeeper.application import RepositoryScope
from notekeeper.application.ports import VoiceSampleRepository
from notekeeper.domain import CampaignId, ParticipantId, VoiceSample, VoiceSampleId
from notekeeper.infrastructure.errors import InfrastructureError

from .database import SQLiteDatabase
from .scope import (
    require_campaign_access,
    require_existing_resource_access,
    workspace_predicate,
)
from .utils import list_voice_samples, save_voice_sample, voice_sample_from_row


class SQLiteVoiceSampleRepository(VoiceSampleRepository):
    def __init__(self, database: SQLiteDatabase, scope: RepositoryScope) -> None:
        self._database = database
        self._scope = scope

    def get(self, voice_sample_id: VoiceSampleId) -> VoiceSample | None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                f"""
                SELECT voice_samples.* FROM voice_samples
                LEFT JOIN campaigns ON campaigns.id = voice_samples.campaign_id
                WHERE voice_samples.id = ? AND {predicate}
                """,
                (str(voice_sample_id), *parameters),
            ).fetchone()
        return voice_sample_from_row(row) if row is not None else None

    def get_by_artifact_uri(
        self,
        campaign_id: CampaignId,
        artifact_uri: str,
    ) -> VoiceSample | None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                f"""
                SELECT voice_samples.* FROM voice_samples
                LEFT JOIN campaigns ON campaigns.id = voice_samples.campaign_id
                WHERE voice_samples.campaign_id = ? AND artifact_uri = ?
                  AND {predicate}
                """,
                (str(campaign_id), artifact_uri, *parameters),
            ).fetchone()
        return voice_sample_from_row(row) if row is not None else None

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[VoiceSample, ...]:
        with self._database.connect() as connection:
            try:
                require_campaign_access(connection, campaign_id, self._scope)
            except InfrastructureError:
                return ()
            return list_voice_samples(connection, campaign_id)

    def list_for_participant(
        self,
        participant_id: ParticipantId,
    ) -> tuple[VoiceSample, ...]:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            rows = connection.execute(
                f"""
                SELECT voice_samples.* FROM voice_samples
                LEFT JOIN campaigns ON campaigns.id = voice_samples.campaign_id
                WHERE participant_id = ? AND {predicate}
                ORDER BY voice_samples.rowid
                """,
                (str(participant_id), *parameters),
            ).fetchall()
        return tuple(voice_sample_from_row(row) for row in rows)

    def save(self, voice_sample: VoiceSample) -> None:
        with self._database.connect() as connection:
            require_campaign_access(connection, voice_sample.campaign_id, self._scope)
            require_existing_resource_access(
                connection,
                self._scope,
                table="voice_samples",
                key_column="id",
                key=str(voice_sample.id),
            )
            save_voice_sample(connection, voice_sample)

    def delete(self, voice_sample_id: VoiceSampleId) -> None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            connection.execute(
                f"""
                DELETE FROM voice_samples WHERE id = ? AND campaign_id IN (
                    SELECT id FROM campaigns WHERE {predicate}
                )
                """,
                (str(voice_sample_id), *parameters),
            )
