"""SQLite recap repository."""

from typing import Any

from notekeeper.application.ports import RecapRepository
from notekeeper.domain import CampaignId, Recap, RecapId, TranscriptId

from ..errors import InfrastructureError
from .database import SQLiteDatabase
from .utils import PayloadStorage
from .utils.serialization import recap_from_payload, recap_to_payload


class SQLiteRecapRepository(RecapRepository):
    def __init__(self, database: SQLiteDatabase, payload_storage: Any) -> None:
        self._database = database
        self._payload_storage = PayloadStorage(payload_storage)

    def get(self, recap_id: RecapId) -> Recap | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM recaps WHERE id = ?",
                (str(recap_id),),
            ).fetchone()
        return self._recap_from_row(row) if row is not None else None

    def list_for_transcript(self, transcript_id: TranscriptId) -> tuple[Recap, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM recaps
                WHERE transcript_id = ?
                ORDER BY rowid
                """,
                (str(transcript_id),),
            ).fetchall()
        return tuple(self._recap_from_row(row) for row in rows)

    def save(self, recap: Recap) -> None:
        campaign_id = self._campaign_id_for_transcript(recap.transcript_id)
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
            connection.execute(
                "DELETE FROM recaps WHERE id = ?",
                (str(recap_id),),
            )

    def payload_uri(self, recap_id: RecapId) -> str | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT payload_uri FROM recaps WHERE id = ?",
                (str(recap_id),),
            ).fetchone()
        return row["payload_uri"] if row is not None else None

    def _campaign_id_for_transcript(self, transcript_id: TranscriptId) -> CampaignId:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT campaign_id FROM transcripts WHERE id = ?",
                (str(transcript_id),),
            ).fetchone()
        if row is None:
            raise InfrastructureError(
                f"cannot save recap for missing transcript: {transcript_id}",
            )
        return CampaignId(row["campaign_id"])

    def _recap_from_row(self, row) -> Recap:
        payload = self._payload_storage.read_json_payload(row["payload_uri"])
        return recap_from_payload(
            recap_id=row["id"],
            transcript_id=row["transcript_id"],
            payload=payload,
        )
