"""Processing job actions for the Textual interface."""

from notekeeper.application import (
    ApplicationError,
    CancelProcessingJobCommand,
    CreateProcessingJobForAudioTrackCommand,
    DeleteProcessingJobCommand,
    RestartProcessingJobCommand,
    RunProcessingJobCommand,
)
from notekeeper.domain import AudioTrack, DomainError, JobStatus, ProcessingJob

from .job_action_confirmation_screen import JobActionConfirmationScreen


def selected_job(app):
    if isinstance(app._selected_object, ProcessingJob):
        return app._selected_object
    return None


def run_selected_job(app) -> None:
    job = selected_job(app)
    if job is None:
        app._set_status("Select a job")
        return
    app.run_worker(
        lambda: app.runtime.use_cases.run_processing_job.execute(
            RunProcessingJobCommand(job_id=str(job.id)),
        ),
        group="job",
        thread=True,
        exit_on_error=False,
    )


def create_job_for_selected_audio_track(app) -> None:
    audio_track = app._selected_object
    if not isinstance(audio_track, AudioTrack):
        app._set_status("Select a recording")
        return

    try:
        result = app.runtime.use_cases.create_processing_job_for_audio_track.execute(
            CreateProcessingJobForAudioTrackCommand(
                audio_track_id=str(audio_track.id),
            ),
        )
        app.refresh_dashboard(update_campaigns=False)
        app._select_job_after_refresh(str(result.job.id))
        app._set_status(f"Created job {result.job.id}")
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))


def restart_selected_failed_job(app) -> None:
    job = selected_job(app)
    if job is None:
        app._set_status("Select a job")
        return
    if job.status not in {JobStatus.FAILED, JobStatus.CANCELED}:
        app._set_status("Job is not failed or canceled")
        return

    try:
        restart_use_case = (
            app.runtime.use_cases.restart_processing_job
            or app.runtime.use_cases.restart_failed_processing_job
        )
        result = restart_use_case.execute(
            RestartProcessingJobCommand(job_id=str(job.id)),
        )
        app.refresh_dashboard(update_campaigns=False)
        app._select_job_after_refresh(str(result.job.id))
        app._set_status(f"Restarted job {job.id} as {result.job.id}")
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))


def confirm_delete_selected_job(app) -> None:
    job = selected_job(app)
    if job is None:
        app._set_status("Select a job")
        return
    app.push_screen(
        JobActionConfirmationScreen("delete", str(job.id)),
        lambda confirmed: _delete_job(app, str(job.id), confirmed),
    )


def _delete_job(app, job_id: str, confirmed: bool) -> None:
    if not confirmed:
        return
    app._job_delete_in_progress = True
    app._update_action_buttons()
    app.run_worker(
        lambda: app.runtime.use_cases.delete_processing_job.execute(
            DeleteProcessingJobCommand(job_id=job_id),
        ),
        group="job-delete",
        thread=True,
        exit_on_error=False,
    )


def confirm_cancel_selected_job(app) -> None:
    job = selected_job(app)
    if job is None:
        app._set_status("Select a job")
        return
    app.push_screen(
        JobActionConfirmationScreen("cancel", str(job.id)),
        lambda confirmed: _cancel_job(app, str(job.id), confirmed),
    )


def _cancel_job(app, job_id: str, confirmed: bool) -> None:
    if not confirmed:
        return
    app._job_cancel_in_progress = True
    app._update_action_buttons()
    app.run_worker(
        lambda: app.runtime.use_cases.cancel_processing_job.execute(
            CancelProcessingJobCommand(job_id=job_id),
        ),
        group="job-cancel",
        thread=True,
        exit_on_error=False,
    )
