"""Local processing-job cleanup across SQLite and filesystem storage."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from notekeeper.application.ports import JobCleaner
from notekeeper.domain import CampaignId, JobStatus, ProcessingJob, ProcessingJobId
from notekeeper.infrastructure.errors import InfrastructureError
from notekeeper.infrastructure.filesystem.storage import LocalCampaignArtifactStorage
from notekeeper.infrastructure.filesystem.utils import ensure_within_root, safe_name
from notekeeper.infrastructure.sqlite.database import SQLiteDatabase


@dataclass(frozen=True, slots=True)
class _CleanupPlan:
    job_ids: tuple[str, ...]
    expected_statuses: tuple[tuple[str, str], ...]


class LocalJobCleaner(JobCleaner):
    def __init__(
        self,
        database: SQLiteDatabase,
        storage: LocalCampaignArtifactStorage,
        processing_work_root: str | Path,
    ) -> None:
        self._database = database
        self._storage = storage
        self._processing_work_root = Path(processing_work_root)

    def clean(
        self,
        campaign_id: CampaignId,
        jobs: tuple[ProcessingJob, ...],
    ) -> tuple[ProcessingJobId, ...]:
        jobs = tuple(jobs)
        if not jobs:
            return ()
        self._validate_jobs(campaign_id, jobs)
        plan = _CleanupPlan(
            job_ids=tuple(str(job.id) for job in jobs),
            expected_statuses=tuple(
                (str(job.id), job.status.value) for job in jobs
            ),
        )
        self._validate_database_rows(campaign_id, plan)
        self._delete_files(campaign_id, plan)
        self._delete_database_rows(campaign_id, plan)
        return tuple(ProcessingJobId(job_id) for job_id in plan.job_ids)

    def _validate_jobs(
        self,
        campaign_id: CampaignId,
        jobs: tuple[ProcessingJob, ...],
    ) -> None:
        if len({str(job.id) for job in jobs}) != len(jobs):
            raise InfrastructureError("job cleanup contains duplicate job ids")
        for job in jobs:
            if job.campaign_id != campaign_id:
                raise InfrastructureError("processing job belongs to another campaign")
            if job.status is JobStatus.RUNNING:
                raise InfrastructureError("running processing job cannot be deleted")

    def _validate_database_rows(
        self,
        campaign_id: CampaignId,
        plan: _CleanupPlan,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        owns_connection = connection is None
        connection = connection or self._database.connect()
        try:
            rows = connection.execute(
                f"""
                SELECT id, campaign_id, status
                FROM jobs
                WHERE id IN ({_placeholders(plan.job_ids)})
                """,
                plan.job_ids,
            ).fetchall()
            rows_by_id = {row["id"]: row for row in rows}
            if set(rows_by_id) != set(plan.job_ids):
                raise InfrastructureError("processing jobs changed before cleanup")
            expected = dict(plan.expected_statuses)
            for job_id, row in rows_by_id.items():
                if row["campaign_id"] != str(campaign_id):
                    raise InfrastructureError(
                        "processing job belongs to another campaign"
                    )
                if row["status"] != expected[job_id]:
                    raise InfrastructureError(
                        "processing job status changed before cleanup"
                    )
        finally:
            if owns_connection:
                connection.close()

    def _delete_files(self, campaign_id: CampaignId, plan: _CleanupPlan) -> None:
        campaign_name = safe_name(str(campaign_id), "campaign_id")
        for job_id in plan.job_ids:
            job_name = safe_name(job_id, "job_id")
            self._remove_path(
                self._storage.path_for_uri(
                    f"{campaign_name}/records/transient/{job_name}",
                ),
                self._storage.storage_root,
            )
            self._remove_path(
                self._processing_work_root / campaign_name / job_name,
                self._processing_work_root,
            )
            self._remove_path(
                self._storage.path_for_uri(
                    f"{campaign_name}/records/manifests/{job_name}",
                ),
                self._storage.storage_root,
            )

    def _delete_database_rows(
        self,
        campaign_id: CampaignId,
        plan: _CleanupPlan,
    ) -> None:
        try:
            with self._database.connect() as connection:
                self._validate_database_rows(campaign_id, plan, connection)
                connection.execute(
                    f"""
                    DELETE FROM speaker_mappings
                    WHERE job_id IN ({_placeholders(plan.job_ids)})
                    """,
                    plan.job_ids,
                )
                connection.execute(
                    f"""
                    DELETE FROM jobs
                    WHERE id IN ({_placeholders(plan.job_ids)})
                    """,
                    plan.job_ids,
                )
        except sqlite3.Error as exc:
            raise InfrastructureError(
                "could not delete processing jobs from the database",
            ) from exc

    def _remove_path(self, path: Path, root: Path) -> None:
        ensure_within_root(path, root)
        if not path.exists() and not path.is_symlink():
            return
        if path.is_symlink():
            raise InfrastructureError(
                "processing job cleanup path must not be a symbolic link",
            )
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            raise InfrastructureError(
                f"could not delete processing job path: {path}",
            ) from exc


def _placeholders(values: tuple[str, ...]) -> str:
    if not values:
        raise InfrastructureError("cleanup query requires at least one identifier")
    return ", ".join("?" for _ in values)


__all__ = ["LocalJobCleaner"]
