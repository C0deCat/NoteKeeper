"""SQLite recap repository."""

import sqlite3
from typing import Any

from notekeeper.application import RepositoryScope
from notekeeper.application.ports import RecapRepository
from notekeeper.domain import CampaignId, Recap, RecapId, TranscriptId

from ..errors import InfrastructureError
from .database import SQLiteDatabase
from .scope import require_existing_resource_access, workspace_predicate
from .utils import PayloadStorage
from .utils.serialization import recap_from_payload, recap_to_payload


class SQLiteRecapRepository(RecapRepository):
    def __init__(
        self,
        database: SQLiteDatabase,
        payload_storage: Any,
        scope: RepositoryScope,
    ) -> None:
        self._database = database
        self._payload_storage = PayloadStorage(payload_storage)
        self._scope = scope

    def get(self, recap_id: RecapId) -> Recap | None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                f"""
                SELECT recaps.* FROM recaps
                LEFT JOIN transcripts ON transcripts.id = recaps.transcript_id
                LEFT JOIN campaigns ON campaigns.id = transcripts.campaign_id
                WHERE recaps.id = ? AND {predicate}
                """,
                (str(recap_id), *parameters),
            ).fetchone()
        return self._recap_from_row(row) if row is not None else None

    def list_for_transcript(self, transcript_id: TranscriptId) -> tuple[Recap, ...]:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            rows = connection.execute(
                f"""
                SELECT recaps.* FROM recaps
                LEFT JOIN transcripts ON transcripts.id = recaps.transcript_id
                LEFT JOIN campaigns ON campaigns.id = transcripts.campaign_id
                WHERE recaps.transcript_id = ? AND {predicate}
                ORDER BY recaps.rowid
                """,
                (str(transcript_id), *parameters),
            ).fetchall()
        return tuple(self._recap_from_row(row) for row in rows)

    def save(self, recap: Recap) -> None:
        campaign_id = self._campaign_id_for_transcript(recap.transcript_id)
        with self._database.connect() as connection:
            require_existing_resource_access(
                connection,
                self._scope,
                table="recaps",
                key_column="id",
                key=str(recap.id),
                campaign_join="""
                LEFT JOIN transcripts ON transcripts.id = recaps.transcript_id
                LEFT JOIN campaigns ON campaigns.id = transcripts.campaign_id
                """,
            )
        artifact = self._payload_storage.save_json_payload(
            campaign_id=campaign_id,
            folder="recaps",
            suggested_name=f"{recap.id}.json",
            payload=recap_to_payload(recap),
        )
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO recaps (id, transcript_id, payload_uri)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    transcript_id = excluded.transcript_id,
                    payload_uri = excluded.payload_uri
                """,
                (str(recap.id), str(recap.transcript_id), artifact.uri),
            )

    def delete(self, recap_id: RecapId) -> None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            connection.execute(
                f"""
                DELETE FROM recaps WHERE id = ? AND transcript_id IN (
                    SELECT transcripts.id FROM transcripts
                    LEFT JOIN campaigns ON campaigns.id = transcripts.campaign_id
                    WHERE {predicate}
                )
                """,
                (str(recap_id), *parameters),
            )

    def payload_uri(self, recap_id: RecapId) -> str | None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                f"""
                SELECT recaps.payload_uri FROM recaps
                LEFT JOIN transcripts ON transcripts.id = recaps.transcript_id
                LEFT JOIN campaigns ON campaigns.id = transcripts.campaign_id
                WHERE recaps.id = ? AND {predicate}
                """,
                (str(recap_id), *parameters),
            ).fetchone()
        return row["payload_uri"] if row is not None else None

    def _campaign_id_for_transcript(self, transcript_id: TranscriptId) -> CampaignId:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                f"""
                SELECT transcripts.campaign_id FROM transcripts
                LEFT JOIN campaigns ON campaigns.id = transcripts.campaign_id
                WHERE transcripts.id = ? AND {predicate}
                """,
                (str(transcript_id), *parameters),
            ).fetchone()
        if row is None:
            raise InfrastructureError(
                f"cannot save recap for missing transcript: {transcript_id}",
            )
        return CampaignId(row["campaign_id"])

    def _recap_from_row(self, row: sqlite3.Row) -> Recap:
        payload = self._payload_storage.read_json_payload(row["payload_uri"])
        return recap_from_payload(
            recap_id=row["id"],
            transcript_id=row["transcript_id"],
            payload=payload,
        )
