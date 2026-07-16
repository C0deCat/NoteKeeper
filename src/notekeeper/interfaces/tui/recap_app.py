"""Recap preview and export actions."""

from notekeeper.application import (
    ApplicationError,
    ExportRecapMarkdownCommand,
    PreviewRecapMarkdownCommand,
)
from notekeeper.domain import DomainError

from .preview_app import MarkdownPreviewScreen


def preview_recap(app) -> None:
    job = app._selected_job()
    if job is None or job.recap_id is None:
        app._set_status("No recap")
        return
    try:
        result = app.runtime.use_cases.preview_recap_markdown.execute(
            PreviewRecapMarkdownCommand(recap_id=str(job.recap_id)),
        )
        app.push_screen(MarkdownPreviewScreen("Recap", result.markdown))
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))


def export_recap(app) -> None:
    job = app._selected_job()
    if job is None or job.recap_id is None:
        app._set_status("No recap")
        return
    try:
        result = app.runtime.use_cases.export_recap_markdown.execute(
            ExportRecapMarkdownCommand(recap_id=str(job.recap_id)),
        )
        location = app.runtime.format_artifact_location(result.artifact)
        app.copy_to_clipboard(location)
        app._set_status(location)
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))
