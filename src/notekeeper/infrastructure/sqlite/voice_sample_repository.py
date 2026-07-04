"""SQLite voice sample repository."""

from notekeeper.application.ports import VoiceSampleRepository
from notekeeper.domain import CampaignId, ParticipantId, VoiceSample, VoiceSampleId

from .database import SQLiteDatabase
from .utils import list_voice_samples, save_voice_sample, voice_sample_from_row


class SQLiteVoiceSampleRepository(VoiceSampleRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def get(self, voice_sample_id: VoiceSampleId) -> VoiceSample | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM voice_samples WHERE id = ?",
                (str(voice_sample_id),),
            ).fetchone()
        return voice_sample_from_row(row) if row is not None else None

    def get_by_artifact_uri(
        self,
        campaign_id: CampaignId,
        artifact_uri: str,
    ) -> VoiceSample | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM voice_samples
                WHERE campaign_id = ? AND artifact_uri = ?
                """,
                (str(campaign_id), artifact_uri),
            ).fetchone()
        return voice_sample_from_row(row) if row is not None else None

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[VoiceSample, ...]:
        with self._database.connect() as connection:
            return list_voice_samples(connection, campaign_id)

    def list_for_participant(
        self,
        participant_id: ParticipantId,
    ) -> tuple[VoiceSample, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM voice_samples
                WHERE participant_id = ?
                ORDER BY rowid
                """,
                (str(participant_id),),
            ).fetchall()
        return tuple(voice_sample_from_row(row) for row in rows)

    def save(self, voice_sample: VoiceSample) -> None:
        with self._database.connect() as connection:
            save_voice_sample(connection, voice_sample)

    def delete(self, voice_sample_id: VoiceSampleId) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM voice_samples WHERE id = ?",
                (str(voice_sample_id),),
            )
