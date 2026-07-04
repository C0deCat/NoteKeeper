"""SQLite transcript repository."""

from typing import Any

from notekeeper.application.ports import TranscriptRepository
from notekeeper.domain import AudioTrackId, CampaignId, Transcript, TranscriptId

from .database import SQLiteDatabase
from .utils import PayloadStorage
from .utils.serialization import transcript_from_payload, transcript_to_payload


class SQLiteTranscriptRepository(TranscriptRepository):
    def __init__(self, database: SQLiteDatabase, payload_storage: Any) -> None:
        self._database = database
        self._payload_storage = PayloadStorage(payload_storage)

    def get(self, transcript_id: TranscriptId) -> Transcript | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM transcripts WHERE id = ?",
                (str(transcript_id),),
            ).fetchone()
        return self._transcript_from_row(row) if row is not None else None

    def list_for_audio_track(
        self,
        audio_track_id: AudioTrackId,
    ) -> tuple[Transcript, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM transcripts
                WHERE audio_track_id = ?
                ORDER BY rowid
                """,
                (str(audio_track_id),),
            ).fetchall()
        return tuple(self._transcript_from_row(row) for row in rows)

    def save(self, transcript: Transcript) -> None:
        artifact = self._payload_storage.save_json_payload(
            campaign_id=CampaignId(transcript.campaign_id),
            folder="transcripts",
            suggested_name=f"{transcript.id}.json",
            payload=transcript_to_payload(transcript),
        )
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO transcripts (
                    id,
                    campaign_id,
                    audio_track_id,
                    payload_uri
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    campaign_id = excluded.campaign_id,
                    audio_track_id = excluded.audio_track_id,
                    payload_uri = excluded.payload_uri
                """,
                (
                    str(transcript.id),
                    str(transcript.campaign_id),
                    str(transcript.audio_track_id),
                    artifact.uri,
                ),
            )

    def delete(self, transcript_id: TranscriptId) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM transcripts WHERE id = ?",
                (str(transcript_id),),
            )

    def payload_uri(self, transcript_id: TranscriptId) -> str | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT payload_uri FROM transcripts WHERE id = ?",
                (str(transcript_id),),
            ).fetchone()
        return row["payload_uri"] if row is not None else None

    def _transcript_from_row(self, row) -> Transcript:
        payload = self._payload_storage.read_json_payload(row["payload_uri"])
        return transcript_from_payload(
            transcript_id=row["id"],
            campaign_id=row["campaign_id"],
            audio_track_id=row["audio_track_id"],
            payload=payload,
        )
