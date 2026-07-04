"""SQLite participant repository."""

from notekeeper.application.ports import ParticipantRepository
from notekeeper.domain import CampaignId, Participant, ParticipantId

from .database import SQLiteDatabase
from .utils import list_participants, participant_from_row, save_participant


class SQLiteParticipantRepository(ParticipantRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def get(self, participant_id: ParticipantId) -> Participant | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, campaign_id, display_name
                FROM participants
                WHERE id = ?
                """,
                (str(participant_id),),
            ).fetchone()
        return participant_from_row(row) if row is not None else None

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[Participant, ...]:
        with self._database.connect() as connection:
            return list_participants(connection, campaign_id)

    def save(self, participant: Participant) -> None:
        with self._database.connect() as connection:
            save_participant(connection, participant)

    def delete(self, participant_id: ParticipantId) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM participants WHERE id = ?",
                (str(participant_id),),
            )
