"""Recap generation, preview, and export actions."""

from notekeeper.application import (
    ApplicationError,
    ExportRecapMarkdownCommand,
    GenerateRecapCommand,
    PreviewRecapMarkdownCommand,
)
from notekeeper.domain import DomainError

from .preview_app import MarkdownPreviewScreen


def recreate_recap(app) -> None:
    job = app._selected_job()
    if job is None or job.transcript_id is None:
        app._set_status("No transcript")
        return
    app._recap_generation_in_progress = True
    app._update_action_buttons()
    app._watch_progress(str(job.id))
    app.run_worker(
        lambda: app.runtime.use_cases.generate_recap.execute(
            GenerateRecapCommand(job_id=str(job.id)),
        ),
        group="recap",
        thread=True,
        exit_on_error=False,
    )


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
