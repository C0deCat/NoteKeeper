"""SQLite processing job repository."""

import json

from notekeeper.application import RepositoryScope, SystemScope
from notekeeper.application.ports import JobRepository
from notekeeper.domain import (
    AudioTrackId,
    CampaignId,
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
)
from notekeeper.infrastructure.errors import InfrastructureError

from .database import SQLiteDatabase
from .scope import (
    require_campaign_access,
    require_existing_resource_access,
    workspace_predicate,
)
from .utils import job_from_row
from .utils.serialization import datetime_to_text, warning_to_dict
from .utils.settings_serialization import processing_settings_to_dict


class SQLiteJobRepository(JobRepository):
    def __init__(self, database: SQLiteDatabase, scope: RepositoryScope) -> None:
        self._database = database
        self._scope = scope

    def get(self, job_id: ProcessingJobId) -> ProcessingJob | None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                f"""
                SELECT jobs.* FROM jobs
                LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                WHERE jobs.id = ? AND {predicate}
                """,
                (str(job_id), *parameters),
            ).fetchone()
        return job_from_row(row) if row is not None else None

    def list_for_campaign(
        self,
        campaign_id: CampaignId,
    ) -> tuple[ProcessingJob, ...]:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            rows = connection.execute(
                f"""
                SELECT jobs.* FROM jobs
                LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                WHERE jobs.campaign_id = ? AND {predicate}
                ORDER BY jobs.rowid
                """,
                (str(campaign_id), *parameters),
            ).fetchall()
        return tuple(job_from_row(row) for row in rows)

    def list_for_audio_track(
        self,
        audio_track_id: AudioTrackId,
    ) -> tuple[ProcessingJob, ...]:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            rows = connection.execute(
                f"""
                SELECT jobs.* FROM jobs
                LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                WHERE jobs.audio_track_id = ? AND {predicate}
                ORDER BY jobs.rowid
                """,
                (str(audio_track_id), *parameters),
            ).fetchall()
        return tuple(job_from_row(row) for row in rows)

    def list_by_statuses(
        self,
        statuses: tuple[JobStatus, ...],
    ) -> tuple[ProcessingJob, ...]:
        statuses = tuple(statuses)
        if not statuses:
            return ()
        placeholders = ", ".join("?" for _ in statuses)
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            rows = connection.execute(
                f"""
                SELECT jobs.* FROM jobs
                LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                WHERE status IN ({placeholders}) AND {predicate}
                ORDER BY updated_at, jobs.rowid
                """,
                (*tuple(status.value for status in statuses), *parameters),
            ).fetchall()
        return tuple(job_from_row(row) for row in rows)

    def has_for_campaign_with_statuses(
        self,
        campaign_id: CampaignId,
        statuses: tuple[JobStatus, ...],
    ) -> bool:
        statuses = tuple(statuses)
        if not statuses:
            return False
        placeholders = ", ".join("?" for _ in statuses)
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            row = connection.execute(
                f"""
                SELECT 1 FROM jobs
                LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                WHERE jobs.campaign_id = ? AND status IN ({placeholders})
                  AND {predicate}
                LIMIT 1
                """,
                (
                    str(campaign_id),
                    *(status.value for status in statuses),
                    *parameters,
                ),
            ).fetchone()
        return row is not None

    def save(self, job: ProcessingJob) -> None:
        with self._database.connect() as connection:
            require_campaign_access(connection, job.campaign_id, self._scope)
            require_existing_resource_access(
                connection,
                self._scope,
                table="jobs",
                key_column="id",
                key=str(job.id),
            )
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
                    error_message,
                    settings_snapshot_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    campaign_id = excluded.campaign_id,
                    audio_track_id = excluded.audio_track_id,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    transcript_id = excluded.transcript_id,
                    recap_id = excluded.recap_id,
                    warnings_json = excluded.warnings_json,
                    error_message = excluded.error_message,
                    settings_snapshot_json = excluded.settings_snapshot_json
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
                    (
                        json.dumps(processing_settings_to_dict(job.settings_snapshot))
                        if job.settings_snapshot is not None
                        else None
                    ),
                ),
            )

    def save_if_status(
        self,
        job: ProcessingJob,
        expected_status: JobStatus,
    ) -> bool:
        with self._database.connect() as connection:
            try:
                require_campaign_access(connection, job.campaign_id, self._scope)
            except InfrastructureError:
                return False
            predicate, parameters = workspace_predicate(self._scope)
            scope_condition = (
                ""
                if isinstance(self._scope, SystemScope)
                else f""" AND campaign_id IN (
                    SELECT id FROM campaigns WHERE {predicate}
                )"""
            )
            cursor = connection.execute(
                f"""
                UPDATE jobs
                SET campaign_id = ?, audio_track_id = ?, status = ?,
                    created_at = ?, updated_at = ?, transcript_id = ?, recap_id = ?,
                    warnings_json = ?, error_message = ?, settings_snapshot_json = ?
                WHERE id = ? AND status = ?{scope_condition}
                """,
                (
                    str(job.campaign_id),
                    str(job.audio_track_id),
                    job.status.value,
                    datetime_to_text(job.created_at),
                    datetime_to_text(job.updated_at),
                    str(job.transcript_id) if job.transcript_id is not None else None,
                    str(job.recap_id) if job.recap_id is not None else None,
                    json.dumps([warning_to_dict(warning) for warning in job.warnings]),
                    job.error_message,
                    (
                        json.dumps(processing_settings_to_dict(job.settings_snapshot))
                        if job.settings_snapshot is not None
                        else None
                    ),
                    str(job.id),
                    expected_status.value,
                    *(parameters if scope_condition else ()),
                ),
            )
            return cursor.rowcount == 1

    def delete(self, job_id: ProcessingJobId) -> None:
        with self._database.connect() as connection:
            predicate, parameters = workspace_predicate(self._scope)
            visible = connection.execute(
                f"""
                SELECT 1 FROM jobs
                LEFT JOIN campaigns ON campaigns.id = jobs.campaign_id
                WHERE jobs.id = ? AND {predicate}
                """,
                (str(job_id), *parameters),
            ).fetchone()
            if visible is None:
                return
            connection.execute(
                "DELETE FROM progress_event_snapshots WHERE operation_id = ?",
                (str(job_id),),
            )
            connection.execute(
                "DELETE FROM jobs WHERE id = ?",
                (str(job_id),),
            )
