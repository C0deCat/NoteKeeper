"""SQLite persistence for queued speaker-review decisions."""

import json
from typing import Any

from notekeeper.application import RepositoryScope, SystemScope
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
from .scope import require_existing_resource_access, workspace_predicate
from notekeeper.infrastructure.errors import InfrastructureError


class SQLiteSpeakerReviewSubmissionRepository(SpeakerReviewSubmissionRepository):
    def __init__(self, database: SQLiteDatabase, scope: RepositoryScope) -> None:
        self._database = database
        self._scope = scope

    def get(
        self,
        job_id: ProcessingJobId,
    ) -> SpeakerReviewSubmission | None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                f"""
                SELECT speaker_review_submissions.*
                FROM speaker_review_submissions
                LEFT JOIN jobs ON jobs.id = speaker_review_submissions.job_id
                LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                WHERE speaker_review_submissions.job_id = ? AND {predicate}
                """,
                (str(job_id), *parameters),
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
            require_existing_resource_access(
                connection,
                self._scope,
                table="speaker_review_submissions",
                key_column="job_id",
                key=str(submission.job_id),
                campaign_join="""
                LEFT JOIN jobs ON jobs.id = speaker_review_submissions.job_id
                LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                """,
            )
            if not isinstance(self._scope, SystemScope):
                predicate, parameters = workspace_predicate(self._scope)
                visible = connection.execute(
                    f"""
                    SELECT 1 FROM jobs
                    LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                    WHERE jobs.id = ? AND {predicate}
                    """,
                    (str(submission.job_id), *parameters),
                ).fetchone()
                if visible is None:
                    raise InfrastructureError(
                        "speaker review job is outside repository scope"
                    )
                references_visible = connection.execute(
                    f"""
                    SELECT 1 FROM jobs
                    JOIN transcripts
                      ON transcripts.id = ?
                     AND transcripts.campaign_id = jobs.campaign_id
                    LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                    WHERE jobs.id = ? AND {predicate}
                    """,
                    (
                        str(submission.transcript_id),
                        str(submission.job_id),
                        *parameters,
                    ),
                ).fetchone()
                if references_visible is None:
                    raise InfrastructureError(
                        "speaker review transcript is outside repository scope"
                    )
                for mapping in submission.mappings:
                    if mapping.participant_id is None:
                        continue
                    participant_visible = connection.execute(
                        f"""
                        SELECT 1 FROM participants
                        JOIN jobs ON jobs.id = ?
                                 AND jobs.campaign_id = participants.campaign_id
                        LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                        WHERE participants.id = ? AND {predicate}
                        """,
                        (
                            str(submission.job_id),
                            str(mapping.participant_id),
                            *parameters,
                        ),
                    ).fetchone()
                    if participant_visible is None:
                        raise InfrastructureError(
                            "speaker review participant is outside repository scope"
                        )
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
            if isinstance(self._scope, SystemScope):
                connection.execute(
                    "DELETE FROM speaker_review_submissions WHERE job_id = ?",
                    (str(job_id),),
                )
                return
            predicate, parameters = workspace_predicate(self._scope)
            connection.execute(
                f"""
                DELETE FROM speaker_review_submissions WHERE job_id = ? AND job_id IN (
                    SELECT jobs.id FROM jobs
                    LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                    WHERE {predicate}
                )
                """,
                (str(job_id), *parameters),
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


def _mapping_from_dict(payload: dict[str, Any]) -> SpeakerMapping:
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
