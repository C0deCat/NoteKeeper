"""Processing job actions for the Textual interface."""

from notekeeper.application import (
    ApplicationError,
    CreateProcessingJobForAudioTrackCommand,
    RestartFailedProcessingJobCommand,
    RunProcessingJobCommand,
)
from notekeeper.domain import AudioTrack, DomainError, JobStatus, ProcessingJob


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
    if job.status is not JobStatus.FAILED:
        app._set_status("Job is not failed")
        return

    try:
        result = app.runtime.use_cases.restart_failed_processing_job.execute(
            RestartFailedProcessingJobCommand(job_id=str(job.id)),
        )
        app.refresh_dashboard(update_campaigns=False)
        app._select_job_after_refresh(str(result.job.id))
        app._set_status(f"Restarted job {job.id} as {result.job.id}")
    except (ApplicationError, DomainError, ValueError) as exc:
        app._set_status(str(exc))
