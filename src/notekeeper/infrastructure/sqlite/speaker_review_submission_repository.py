"""SQLite persistence for queued speaker-review decisions."""

import json

from notekeeper.application.ports import SpeakerReviewSubmissionRepository
from notekeeper.application.results import SpeakerReviewSubmission
from notekeeper.domain import (
    ParticipantId,
    ProcessingJobId,
    SpeakerLabel,
    SpeakerMapping,
    SpeakerMappingSource,
    SpeakerMappingStatus,
    TranscriptId,
)

from .database import SQLiteDatabase


class SQLiteSpeakerReviewSubmissionRepository(SpeakerReviewSubmissionRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def get(
        self,
        job_id: ProcessingJobId,
    ) -> SpeakerReviewSubmission | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM speaker_review_submissions WHERE job_id = ?",
                (str(job_id),),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["mappings_json"])
        return SpeakerReviewSubmission(
            job_id=ProcessingJobId(row["job_id"]),
            transcript_id=TranscriptId(row["transcript_id"]),
            mappings=tuple(_mapping_from_dict(item) for item in payload),
        )

    def save(self, submission: SpeakerReviewSubmission) -> None:
        payload = [_mapping_to_dict(mapping) for mapping in submission.mappings]
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO speaker_review_submissions (
                    job_id, transcript_id, mappings_json
                ) VALUES (?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    transcript_id = excluded.transcript_id,
                    mappings_json = excluded.mappings_json
                """,
                (
                    str(submission.job_id),
                    str(submission.transcript_id),
                    json.dumps(payload, sort_keys=True),
                ),
            )

    def delete(self, job_id: ProcessingJobId) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM speaker_review_submissions WHERE job_id = ?",
                (str(job_id),),
            )


def _mapping_to_dict(mapping: SpeakerMapping) -> dict[str, object]:
    return {
        "anonymous_label": mapping.anonymous_label.value,
        "named_label": (
            mapping.named_label.value if mapping.named_label is not None else None
        ),
        "participant_id": (
            str(mapping.participant_id) if mapping.participant_id is not None else None
        ),
        "confidence": mapping.confidence,
        "source": mapping.source.value,
        "status": mapping.status.value,
    }


def _mapping_from_dict(payload: dict[str, object]) -> SpeakerMapping:
    named_label = payload.get("named_label")
    participant_id = payload.get("participant_id")
    return SpeakerMapping(
        anonymous_label=SpeakerLabel.anonymous(str(payload["anonymous_label"])),
        named_label=(
            SpeakerLabel.named(str(named_label)) if named_label is not None else None
        ),
        participant_id=(
            ParticipantId(str(participant_id)) if participant_id is not None else None
        ),
        confidence=(
            float(payload["confidence"])
            if payload.get("confidence") is not None
            else None
        ),
        source=SpeakerMappingSource(str(payload["source"])),
        status=SpeakerMappingStatus(str(payload["status"])),
    )


__all__ = ["SQLiteSpeakerReviewSubmissionRepository"]
