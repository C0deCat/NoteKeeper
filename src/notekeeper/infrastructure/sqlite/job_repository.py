"""SQLite processing job repository."""

import json

from notekeeper.domain import (
    AudioTrackId,
    CampaignId,
    ProcessingJob,
    ProcessingJobId,
)

from .database import SQLiteDatabase
from .utils import job_from_row
from .utils.serialization import datetime_to_text, warning_to_dict


class SQLiteJobRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def get(self, job_id: ProcessingJobId) -> ProcessingJob | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (str(job_id),),
            ).fetchone()
        return job_from_row(row) if row is not None else None

    def list_for_campaign(
        self,
        campaign_id: CampaignId,
    ) -> tuple[ProcessingJob, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM jobs
                WHERE campaign_id = ?
                ORDER BY rowid
                """,
                (str(campaign_id),),
            ).fetchall()
        return tuple(job_from_row(row) for row in rows)

    def list_for_audio_track(
        self,
        audio_track_id: AudioTrackId,
    ) -> tuple[ProcessingJob, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM jobs
                WHERE audio_track_id = ?
                ORDER BY rowid
                """,
                (str(audio_track_id),),
            ).fetchall()
        return tuple(job_from_row(row) for row in rows)

    def save(self, job: ProcessingJob) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id,
                    campaign_id,
                    audio_track_id,
                    status,
                    created_at,
                    updated_at,
                    transcript_id,
                    recap_id,
                    warnings_json,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    campaign_id = excluded.campaign_id,
                    audio_track_id = excluded.audio_track_id,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    transcript_id = excluded.transcript_id,
                    recap_id = excluded.recap_id,
                    warnings_json = excluded.warnings_json,
                    error_message = excluded.error_message
                """,
                (
                    str(job.id),
                    str(job.campaign_id),
                    str(job.audio_track_id),
                    job.status.value,
                    datetime_to_text(job.created_at),
                    datetime_to_text(job.updated_at),
                    str(job.transcript_id) if job.transcript_id is not None else None,
                    str(job.recap_id) if job.recap_id is not None else None,
                    json.dumps([warning_to_dict(warning) for warning in job.warnings]),
                    job.error_message,
                ),
            )

    def delete(self, job_id: ProcessingJobId) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM jobs WHERE id = ?",
                (str(job_id),),
            )
