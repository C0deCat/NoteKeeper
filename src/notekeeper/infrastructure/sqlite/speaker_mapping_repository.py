"""SQLite speaker mapping repository."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from notekeeper.application import RepositoryScope, SystemScope
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
from .scope import workspace_predicate


class SQLiteSpeakerMappingRepository(SpeakerMappingRepository):
    def __init__(self, database: SQLiteDatabase, scope: RepositoryScope) -> None:
        self._database = database
        self._scope = scope

    def save_many(self, records: tuple[SpeakerMappingRecord, ...]) -> None:
        records = tuple(records)
        if not records:
            return

        with self._database.connect() as connection:
            if not isinstance(self._scope, SystemScope):
                for record in records:
                    self._require_record_access(connection, record)
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

    def _require_record_access(
        self,
        connection: sqlite3.Connection,
        record: SpeakerMappingRecord,
    ) -> None:
        predicate, parameters = workspace_predicate(self._scope)
        visible = connection.execute(
            f"""
            SELECT 1 FROM jobs
            JOIN transcripts
              ON transcripts.id = ?
             AND transcripts.campaign_id = jobs.campaign_id
            LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
            WHERE jobs.id = ? AND {predicate}
            """,
            (str(record.transcript_id), str(record.job_id), *parameters),
        ).fetchone()
        if visible is None:
            raise InfrastructureError(
                "speaker mappings reference resources outside repository scope"
            )
        participant_id = record.mapping.participant_id
        if participant_id is None:
            return
        participant_visible = connection.execute(
            f"""
            SELECT 1 FROM participants
            JOIN jobs ON jobs.id = ?
                     AND jobs.campaign_id = participants.campaign_id
            LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
            WHERE participants.id = ? AND {predicate}
            """,
            (str(record.job_id), str(participant_id), *parameters),
        ).fetchone()
        if participant_visible is None:
            raise InfrastructureError(
                "speaker mapping participant is outside repository scope"
            )

    def list_for_job(
        self,
        job_id: ProcessingJobId,
    ) -> tuple[SpeakerMappingRecord, ...]:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            rows = connection.execute(
                f"""
                SELECT speaker_mappings.* FROM speaker_mappings
                LEFT JOIN jobs ON jobs.id = speaker_mappings.job_id
                LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                WHERE speaker_mappings.job_id = ? AND {predicate}
                ORDER BY speaker_mappings.id
                """,
                (str(job_id), *parameters),
            ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def list_for_transcript(
        self,
        transcript_id: TranscriptId,
    ) -> tuple[SpeakerMappingRecord, ...]:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            rows = connection.execute(
                f"""
                SELECT speaker_mappings.* FROM speaker_mappings
                LEFT JOIN jobs ON jobs.id = speaker_mappings.job_id
                LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                WHERE speaker_mappings.transcript_id = ? AND {predicate}
                ORDER BY speaker_mappings.id
                """,
                (str(transcript_id), *parameters),
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


def _record_from_row(row: sqlite3.Row) -> SpeakerMappingRecord:
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
