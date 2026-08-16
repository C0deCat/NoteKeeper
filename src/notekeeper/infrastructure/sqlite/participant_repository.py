"""SQLite participant repository."""

from notekeeper.application import RepositoryScope
from notekeeper.application.ports import ParticipantRepository
from notekeeper.domain import CampaignId, Participant, ParticipantId
from notekeeper.infrastructure.errors import InfrastructureError

from .database import SQLiteDatabase
from .scope import (
    require_campaign_access,
    require_existing_resource_access,
    workspace_predicate,
)
from .utils import list_participants, participant_from_row, save_participant


class SQLiteParticipantRepository(ParticipantRepository):
    def __init__(self, database: SQLiteDatabase, scope: RepositoryScope) -> None:
        self._database = database
        self._scope = scope

    def get(self, participant_id: ParticipantId) -> Participant | None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                """
                SELECT participants.id, participants.campaign_id,
                       participants.display_name
                FROM participants
                LEFT JOIN campaigns ON campaigns.id = participants.campaign_id
                WHERE participants.id = ? AND """
                + predicate,
                (str(participant_id), *parameters),
            ).fetchone()
        return participant_from_row(row) if row is not None else None

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[Participant, ...]:
        with self._database.connect() as connection:
            try:
                require_campaign_access(connection, campaign_id, self._scope)
            except InfrastructureError:
                return ()
            return list_participants(connection, campaign_id)

    def save(self, participant: Participant) -> None:
        with self._database.connect() as connection:
            require_campaign_access(connection, participant.campaign_id, self._scope)
            require_existing_resource_access(
                connection,
                self._scope,
                table="participants",
                key_column="id",
                key=str(participant.id),
            )
            save_participant(connection, participant)

    def delete(self, participant_id: ParticipantId) -> None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            connection.execute(
                f"""
                DELETE FROM participants WHERE id = ? AND campaign_id IN (
                    SELECT id FROM campaigns WHERE {predicate}
                )
                """,
                (str(participant_id), *parameters),
            )
