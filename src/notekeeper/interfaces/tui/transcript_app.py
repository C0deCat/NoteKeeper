"""Transcript preview and export actions."""

from notekeeper.application import (
    ApplicationError,
    ExportTranscriptMarkdownCommand,
    PreviewTranscriptMarkdownCommand,
)
from notekeeper.domain import DomainError

from .preview_app import MarkdownPreviewScreen


def preview_transcript(app) -> None:
    job = app._selected_job()
    if job is None or job.transcript_id is None:
        app._set_status("No transcript")
        return
    try:
        result = app.runtime.use_cases.preview_transcript_markdown.execute(
            PreviewTranscriptMarkdownCommand(transcript_id=str(job.transcript_id)),
        )
        app.push_screen(MarkdownPreviewScreen("Transcript", result.markdown))
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))


def export_transcript(app) -> None:
    job = app._selected_job()
    if job is None or job.transcript_id is None:
        app._set_status("No transcript")
        return
    try:
        result = app.runtime.use_cases.export_transcript_markdown.execute(
            ExportTranscriptMarkdownCommand(transcript_id=str(job.transcript_id)),
        )
        location = app.runtime.format_artifact_location(result.artifact)
        app.copy_to_clipboard(location)
        app._set_status(location)
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))
