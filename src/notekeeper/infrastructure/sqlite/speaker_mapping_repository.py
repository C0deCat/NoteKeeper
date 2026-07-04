"""SQLite speaker mapping repository."""

from __future__ import annotations

import json
from typing import Any

from notekeeper.application.ports import SpeakerMappingRepository
from notekeeper.application.results import SpeakerMappingRecord
from notekeeper.domain import (
    ParticipantId,
    ProcessingJobId,
    SpeakerLabel,
    SpeakerMapping,
    SpeakerMappingSource,
    SpeakerMappingStatus,
    TranscriptId,
)
from notekeeper.infrastructure.errors import InfrastructureError

from .database import SQLiteDatabase


class SQLiteSpeakerMappingRepository(SpeakerMappingRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def save_many(self, records: tuple[SpeakerMappingRecord, ...]) -> None:
        records = tuple(records)
        if not records:
            return

        with self._database.connect() as connection:
            connection.executemany(
                """
                INSERT INTO speaker_mappings (
                    job_id,
                    transcript_id,
                    anonymous_label,
                    participant_id,
                    named_label,
                    confidence,
                    source,
                    status,
                    diagnostics_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(_record_to_row(record) for record in records),
            )

    def list_for_job(
        self,
        job_id: ProcessingJobId,
    ) -> tuple[SpeakerMappingRecord, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM speaker_mappings
                WHERE job_id = ?
                ORDER BY id
                """,
                (str(job_id),),
            ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def list_for_transcript(
        self,
        transcript_id: TranscriptId,
    ) -> tuple[SpeakerMappingRecord, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM speaker_mappings
                WHERE transcript_id = ?
                ORDER BY id
                """,
                (str(transcript_id),),
            ).fetchall()
        return tuple(_record_from_row(row) for row in rows)


def _record_to_row(record: SpeakerMappingRecord) -> tuple[Any, ...]:
    mapping = record.mapping
    return (
        str(record.job_id),
        str(record.transcript_id),
        mapping.anonymous_label.value,
        str(mapping.participant_id) if mapping.participant_id is not None else None,
        mapping.named_label.value if mapping.named_label is not None else None,
        mapping.confidence,
        mapping.source.value,
        mapping.status.value,
        json.dumps(record.diagnostics, sort_keys=True),
    )


def _record_from_row(row) -> SpeakerMappingRecord:
    diagnostics = json.loads(row["diagnostics_json"])
    if not isinstance(diagnostics, dict):
        raise InfrastructureError("speaker mapping diagnostics must be a JSON object")

    return SpeakerMappingRecord(
        job_id=ProcessingJobId(row["job_id"]),
        transcript_id=TranscriptId(row["transcript_id"]),
        mapping=SpeakerMapping(
            anonymous_label=SpeakerLabel.anonymous(row["anonymous_label"]),
            named_label=(
                SpeakerLabel.named(row["named_label"])
                if row["named_label"] is not None
                else None
            ),
            participant_id=(
                ParticipantId(row["participant_id"])
                if row["participant_id"] is not None
                else None
            ),
            confidence=row["confidence"],
            source=SpeakerMappingSource(row["source"]),
            status=SpeakerMappingStatus(row["status"]),
        ),
        diagnostics=diagnostics,
    )
