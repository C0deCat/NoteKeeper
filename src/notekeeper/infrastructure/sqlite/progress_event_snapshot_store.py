"""SQLite persistence for cross-runtime progress snapshots."""

from notekeeper.application.ports import ProgressEventSnapshotStore
from notekeeper.application.results import ProgressEvent, ProgressEventKind
from notekeeper.domain import ProgressBar

from .database import SQLiteDatabase


class SQLiteProgressEventSnapshotStore(ProgressEventSnapshotStore):
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def get(self, operation_id: str) -> ProgressEvent | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM progress_event_snapshots WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        if row is None:
            return None
        return ProgressEvent(
            operation_id=row["operation_id"],
            stage_index=row["stage_index"],
            stage_count=row["stage_count"],
            timing_available=bool(row["timing_available"]),
            kind=ProgressEventKind(row["event_kind"]),
            progress=ProgressBar(
                stage=row["progress_stage"],
                expected_duration=row["expected_duration"],
                current_duration=row["current_duration"],
            ),
        )

    def save(self, event: ProgressEvent) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO progress_event_snapshots (
                    operation_id,
                    event_kind,
                    stage_index,
                    stage_count,
                    timing_available,
                    progress_stage,
                    expected_duration,
                    current_duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(operation_id) DO UPDATE SET
                    event_kind = excluded.event_kind,
                    stage_index = excluded.stage_index,
                    stage_count = excluded.stage_count,
                    timing_available = excluded.timing_available,
                    progress_stage = excluded.progress_stage,
                    expected_duration = excluded.expected_duration,
                    current_duration = excluded.current_duration
                """,
                (
                    event.operation_id,
                    event.kind.value,
                    event.stage_index,
                    event.stage_count,
                    int(event.timing_available),
                    event.progress.stage,
                    event.progress.expected_duration,
                    event.progress.current_duration,
                ),
            )

    def delete(self, operation_id: str) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM progress_event_snapshots WHERE operation_id = ?",
                (operation_id,),
            )


__all__ = ["SQLiteProgressEventSnapshotStore"]
