"""Transcript preview and export actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from notekeeper.application import (
    ApplicationError,
    ExportTranscriptMarkdownCommand,
    PreviewTranscriptMarkdownCommand,
)
from notekeeper.domain import DomainError

from .preview_app import MarkdownPreviewScreen

if TYPE_CHECKING:
    from .tui import NoteKeeperTui


def preview_transcript(app: NoteKeeperTui) -> None:
    job = app._selected_job()
    if job is None or job.transcript_id is None:
        app._write_ui_log("No transcript")
        return
    try:
        result = app.runtime.use_cases.transcripts.preview_markdown.execute(
            PreviewTranscriptMarkdownCommand(transcript_id=str(job.transcript_id)),
        )
        app.push_screen(MarkdownPreviewScreen("Transcript", result.markdown))
    except (ApplicationError, DomainError, ValueError) as exc:
        app._write_ui_log(str(exc))


def export_transcript(app: NoteKeeperTui) -> None:
    job = app._selected_job()
    if job is None or job.transcript_id is None:
        app._write_ui_log("No transcript")
        return
    try:
        result = app.runtime.use_cases.transcripts.export_markdown.execute(
            ExportTranscriptMarkdownCommand(transcript_id=str(job.transcript_id)),
        )
        location = app.runtime.format_artifact_location(result.artifact)
        app.copy_to_clipboard(location)
        app._write_ui_log(location)
    except (ApplicationError, DomainError, ValueError) as exc:
        app._write_ui_log(str(exc))
