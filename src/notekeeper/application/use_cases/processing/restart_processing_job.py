"""Restart a failed or canceled processing job as a new pending job."""

from notekeeper.application.commands import RestartProcessingJobCommand
from notekeeper.application.errors import InvalidOperationError, NotFoundError
from notekeeper.application.ports import (
    AudioTrackRepository,
    CampaignRepository,
    Clock,
    IdGenerator,
    JobRepository,
)
from notekeeper.application.results import RestartProcessingJobResult
from notekeeper.application.settings_service import SettingsService
from notekeeper.application.use_cases.utils import (
    require_audio_track,
    require_campaign,
    require_job,
)
from notekeeper.domain import (
    DomainValidationError,
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
    ensure_campaign_ready_for_processing,
    ensure_processing_job_can_be_restarted,
)


class RestartProcessingJob:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        audio_track_repository: AudioTrackRepository,
        job_repository: JobRepository,
        clock: Clock,
        id_generator: IdGenerator,
        settings_service: SettingsService | None = None,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._audio_track_repository = audio_track_repository
        self._job_repository = job_repository
        self._clock = clock
        self._id_generator = id_generator
        self._settings_service = settings_service

    def execute(
        self,
        command: RestartProcessingJobCommand,
    ) -> RestartProcessingJobResult:
        source_job = require_job(
            self._job_repository,
            ProcessingJobId(command.job_id),
        )
        try:
            ensure_processing_job_can_be_restarted(source_job)
        except DomainValidationError as exc:
            raise InvalidOperationError(str(exc)) from exc

        campaign = require_campaign(self._campaign_repository, source_job.campaign_id)
        audio_track = require_audio_track(
            self._audio_track_repository,
            source_job.audio_track_id,
        )
        if audio_track.campaign_id != campaign.id:
            raise NotFoundError(
                f"audio track {audio_track.id} was not found in campaign {campaign.id}",
            )
        if all(track.id != audio_track.id for track in campaign.audio_tracks):
            raise NotFoundError(
                f"audio track {audio_track.id} was not found in campaign {campaign.id}",
            )

        ensure_campaign_ready_for_processing(campaign)

        now = self._clock.now()
        job = ProcessingJob(
            id=ProcessingJobId(self._id_generator.processing_job_id()),
            campaign_id=source_job.campaign_id,
            audio_track_id=source_job.audio_track_id,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
            settings_snapshot=(
                source_job.settings_snapshot
                or (
                    self._settings_service.snapshot_for_campaign(str(campaign.id))
                    if self._settings_service is not None
                    else None
                )
            ),
        )
        self._job_repository.save(job)
        return RestartProcessingJobResult(
            campaign=campaign,
            audio_track=audio_track,
            source_job=source_job,
            job=job,
        )


RestartFailedProcessingJob = RestartProcessingJob

__all__ = ["RestartFailedProcessingJob", "RestartProcessingJob"]
