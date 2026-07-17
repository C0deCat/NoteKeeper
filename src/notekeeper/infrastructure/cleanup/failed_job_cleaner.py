"""Local failed-job cleanup across SQLite and filesystem storage."""

from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from notekeeper.application.ports import FailedJobCleaner
from notekeeper.domain import (
    CampaignId,
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
)
from notekeeper.infrastructure.errors import InfrastructureError
from notekeeper.infrastructure.filesystem.storage import LocalCampaignArtifactStorage
from notekeeper.infrastructure.filesystem.utils import ensure_within_root, safe_name
from notekeeper.infrastructure.sqlite.database import SQLiteDatabase


@dataclass(frozen=True, slots=True)
class _CleanupPlan:
    job_ids: tuple[str, ...]
    transcript_ids: tuple[str, ...]
    recap_ids: tuple[str, ...]
    payload_uris: tuple[str, ...]


class LocalFailedJobCleaner(FailedJobCleaner):
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

        job_ids = tuple(str(job.id) for job in jobs)
        plan = self._build_plan(campaign_id, job_ids)
        self._delete_files(campaign_id, plan)
        self._delete_database_rows(campaign_id, plan)
        return tuple(ProcessingJobId(job_id) for job_id in plan.job_ids)

    def _validate_jobs(
        self,
        campaign_id: CampaignId,
        jobs: tuple[ProcessingJob, ...],
    ) -> None:
        if len({str(job.id) for job in jobs}) != len(jobs):
            raise InfrastructureError("failed job cleanup contains duplicate job ids")
        for job in jobs:
            if job.campaign_id != campaign_id:
                raise InfrastructureError("failed job belongs to another campaign")
            if job.status is not JobStatus.FAILED:
                raise InfrastructureError("only failed jobs can be cleaned")

    def _build_plan(
        self,
        campaign_id: CampaignId,
        job_ids: tuple[str, ...],
    ) -> _CleanupPlan:
        job_placeholders = _placeholders(job_ids)
        with self._database.connect() as connection:
            job_rows = connection.execute(
                f"""
                SELECT id, campaign_id, status, transcript_id
                FROM jobs
                WHERE id IN ({job_placeholders})
                """,
                job_ids,
            ).fetchall()
            self._validate_job_rows(campaign_id, job_ids, job_rows)

            candidate_transcript_ids = tuple(
                sorted(
                    {
                        row["transcript_id"]
                        for row in job_rows
                        if row["transcript_id"] is not None
                    },
                ),
            )
            transcript_ids = self._exclusive_transcript_ids(
                connection,
                job_ids,
                candidate_transcript_ids,
            )
            transcript_rows = self._transcript_rows(connection, transcript_ids)
            recap_rows = self._recap_rows(connection, transcript_ids)

        payload_uris = tuple(
            sorted(
                {
                    row["payload_uri"]
                    for row in (*transcript_rows, *recap_rows)
                    if row["payload_uri"]
                },
            ),
        )
        return _CleanupPlan(
            job_ids=job_ids,
            transcript_ids=transcript_ids,
            recap_ids=tuple(sorted(row["id"] for row in recap_rows)),
            payload_uris=payload_uris,
        )

    def _validate_job_rows(
        self,
        campaign_id: CampaignId,
        job_ids: tuple[str, ...],
        rows,
    ) -> None:
        rows_by_id = {row["id"]: row for row in rows}
        if set(rows_by_id) != set(job_ids):
            raise InfrastructureError("failed jobs changed before cleanup")
        for row in rows:
            if row["campaign_id"] != str(campaign_id):
                raise InfrastructureError("failed job belongs to another campaign")
            if row["status"] != JobStatus.FAILED.value:
                raise InfrastructureError("processing job is no longer failed")

    def _exclusive_transcript_ids(
        self,
        connection: sqlite3.Connection,
        job_ids: tuple[str, ...],
        transcript_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        if not transcript_ids:
            return ()

        transcript_placeholders = _placeholders(transcript_ids)
        job_placeholders = _placeholders(job_ids)
        external_job_rows = connection.execute(
            f"""
            SELECT DISTINCT transcript_id
            FROM jobs
            WHERE transcript_id IN ({transcript_placeholders})
              AND id NOT IN ({job_placeholders})
            """,
            (*transcript_ids, *job_ids),
        ).fetchall()
        external_mapping_rows = connection.execute(
            f"""
            SELECT DISTINCT transcript_id
            FROM speaker_mappings
            WHERE transcript_id IN ({transcript_placeholders})
              AND job_id NOT IN ({job_placeholders})
            """,
            (*transcript_ids, *job_ids),
        ).fetchall()
        external_recap_rows = connection.execute(
            f"""
            SELECT DISTINCT recaps.transcript_id
            FROM recaps
            JOIN jobs ON jobs.recap_id = recaps.id
            WHERE recaps.transcript_id IN ({transcript_placeholders})
              AND jobs.id NOT IN ({job_placeholders})
            """,
            (*transcript_ids, *job_ids),
        ).fetchall()
        shared_ids = {
            row["transcript_id"]
            for row in (
                *external_job_rows,
                *external_mapping_rows,
                *external_recap_rows,
            )
        }
        return tuple(
            transcript_id
            for transcript_id in transcript_ids
            if transcript_id not in shared_ids
        )

    def _transcript_rows(
        self,
        connection: sqlite3.Connection,
        transcript_ids: tuple[str, ...],
    ):
        if not transcript_ids:
            return ()
        return tuple(
            connection.execute(
                f"""
                SELECT id, payload_uri
                FROM transcripts
                WHERE id IN ({_placeholders(transcript_ids)})
                """,
                transcript_ids,
            ).fetchall(),
        )

    def _recap_rows(
        self,
        connection: sqlite3.Connection,
        transcript_ids: tuple[str, ...],
    ):
        if not transcript_ids:
            return ()
        return tuple(
            connection.execute(
                f"""
                SELECT id, transcript_id, payload_uri
                FROM recaps
                WHERE transcript_id IN ({_placeholders(transcript_ids)})
                """,
                transcript_ids,
            ).fetchall(),
        )

    def _delete_files(
        self,
        campaign_id: CampaignId,
        plan: _CleanupPlan,
    ) -> None:
        campaign_name = safe_name(str(campaign_id), "campaign_id")
        for job_id in plan.job_ids:
            job_name = safe_name(job_id, "job_id")
            self._remove_path(
                self._storage.path_for_uri(
                    f"{campaign_name}/records/prepared/{job_name}",
                ),
                self._storage.storage_root,
            )
            self._remove_path(
                self._processing_work_root / campaign_name / job_name,
                self._processing_work_root,
            )

        for payload_uri in plan.payload_uris:
            self._remove_path(
                self._storage.path_for_uri(payload_uri),
                self._storage.storage_root,
            )

        for transcript_id in plan.transcript_ids:
            transcript_name = safe_name(transcript_id, "transcript_id")
            for uri in (
                f"{campaign_name}/transcripts/raw-whisperx/{transcript_name}.json",
                f"transcript-{transcript_name}.md",
            ):
                self._remove_path(
                    self._storage.path_for_uri(uri),
                    self._storage.storage_root,
                )

        for recap_id in plan.recap_ids:
            recap_name = safe_name(recap_id, "recap_id")
            self._remove_path(
                self._storage.path_for_uri(f"recap-{recap_name}.md"),
                self._storage.storage_root,
            )

        self._delete_orphan_raw_transcripts(campaign_id, set(plan.job_ids))
        self._delete_job_diagnostics(campaign_id, set(plan.job_ids))

    def _delete_orphan_raw_transcripts(
        self,
        campaign_id: CampaignId,
        job_ids: set[str],
    ) -> None:
        campaign_name = safe_name(str(campaign_id), "campaign_id")
        raw_root = self._storage.path_for_uri(
            f"{campaign_name}/transcripts/raw-whisperx",
        )
        if not raw_root.exists() and not raw_root.is_symlink():
            return
        if raw_root.is_symlink():
            raise InfrastructureError(
                "failed job cleanup path must not be a symbolic link",
            )

        prepared_prefixes = tuple(
            f"{campaign_name}/records/prepared/{safe_name(job_id, 'job_id')}/"
            for job_id in job_ids
        )
        for payload_path in tuple(raw_root.glob("*.json")):
            if payload_path.is_symlink():
                continue
            try:
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            audio_artifact = payload.get("audio_artifact")
            audio_uri = (
                audio_artifact.get("uri")
                if isinstance(audio_artifact, dict)
                else None
            )
            if isinstance(audio_uri, str) and audio_uri.startswith(
                prepared_prefixes,
            ):
                self._remove_path(payload_path, self._storage.storage_root)

        self._remove_empty_directory(raw_root, self._storage.storage_root)

    def _delete_job_diagnostics(
        self,
        campaign_id: CampaignId,
        job_ids: set[str],
    ) -> None:
        campaign_name = safe_name(str(campaign_id), "campaign_id")
        diagnostics_root = self._storage.path_for_uri(
            f"{campaign_name}/recaps/llm-diagnostics",
        )
        if not diagnostics_root.exists() and not diagnostics_root.is_symlink():
            return
        if diagnostics_root.is_symlink():
            raise InfrastructureError(
                "failed job cleanup path must not be a symbolic link",
            )

        for recap_directory in tuple(diagnostics_root.iterdir()):
            if not recap_directory.is_dir() or recap_directory.is_symlink():
                continue
            if self._diagnostics_belong_to_job(recap_directory, job_ids):
                self._remove_path(recap_directory, self._storage.storage_root)

        self._remove_empty_directory(diagnostics_root, self._storage.storage_root)

    def _diagnostics_belong_to_job(
        self,
        directory: Path,
        job_ids: set[str],
    ) -> bool:
        for payload_path in directory.rglob("*.json"):
            if payload_path.is_symlink():
                continue
            try:
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            context = payload.get("context")
            if isinstance(context, dict) and context.get("job_id") in job_ids:
                return True
        return False

    def _delete_database_rows(
        self,
        campaign_id: CampaignId,
        plan: _CleanupPlan,
    ) -> None:
        try:
            with self._database.connect() as connection:
                job_rows = connection.execute(
                    f"""
                    SELECT id, campaign_id, status, transcript_id
                    FROM jobs
                    WHERE id IN ({_placeholders(plan.job_ids)})
                    """,
                    plan.job_ids,
                ).fetchall()
                self._validate_job_rows(campaign_id, plan.job_ids, job_rows)
                current_transcript_ids = self._exclusive_transcript_ids(
                    connection,
                    plan.job_ids,
                    plan.transcript_ids,
                )
                if current_transcript_ids != plan.transcript_ids:
                    raise InfrastructureError(
                        "failed job relationships changed before cleanup",
                    )

                connection.execute(
                    f"""
                    DELETE FROM speaker_mappings
                    WHERE job_id IN ({_placeholders(plan.job_ids)})
                    """,
                    plan.job_ids,
                )
                if plan.recap_ids:
                    connection.execute(
                        f"""
                        DELETE FROM recaps
                        WHERE id IN ({_placeholders(plan.recap_ids)})
                        """,
                        plan.recap_ids,
                    )
                if plan.transcript_ids:
                    connection.execute(
                        f"""
                        DELETE FROM transcripts
                        WHERE id IN ({_placeholders(plan.transcript_ids)})
                        """,
                        plan.transcript_ids,
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
                "could not delete failed jobs from the database",
            ) from exc

    def _remove_path(self, path: Path, root: Path) -> None:
        ensure_within_root(path, root)
        if not path.exists() and not path.is_symlink():
            return
        if path.is_symlink():
            raise InfrastructureError(
                "failed job cleanup path must not be a symbolic link",
            )
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            raise InfrastructureError(
                f"could not delete failed job path: {path}",
            ) from exc

    def _remove_empty_directory(self, path: Path, root: Path) -> None:
        ensure_within_root(path, root)
        try:
            path.rmdir()
        except FileNotFoundError:
            return
        except OSError:
            if path.is_dir() and any(path.iterdir()):
                return
            raise InfrastructureError(
                f"could not remove empty failed job directory: {path}",
            )


def _placeholders(values: tuple[str, ...]) -> str:
    if not values:
        raise InfrastructureError("cleanup query requires at least one identifier")
    return ", ".join("?" for _ in values)
