"""Restart a failed processing job as a new pending job."""

from notekeeper.application.commands import RestartFailedProcessingJobCommand
from notekeeper.application.errors import InvalidOperationError, NotFoundError
from notekeeper.application.ports import (
    AudioTrackRepository,
    CampaignRepository,
    Clock,
    IdGenerator,
    JobRepository,
)
from notekeeper.application.results import RestartFailedProcessingJobResult
from notekeeper.application.use_cases.utils import (
    _require_audio_track,
    _require_campaign,
    _require_job,
)
from notekeeper.domain import (
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
    ensure_campaign_ready_for_processing,
)


class RestartFailedProcessingJob:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        audio_track_repository: AudioTrackRepository,
        job_repository: JobRepository,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._audio_track_repository = audio_track_repository
        self._job_repository = job_repository
        self._clock = clock
        self._id_generator = id_generator

    def execute(
        self,
        command: RestartFailedProcessingJobCommand,
    ) -> RestartFailedProcessingJobResult:
        source_job = _require_job(
            self._job_repository,
            ProcessingJobId(command.job_id),
        )
        if source_job.status is not JobStatus.FAILED:
            raise InvalidOperationError("processing job must be failed")

        campaign = _require_campaign(self._campaign_repository, source_job.campaign_id)
        audio_track = _require_audio_track(
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
        )
        self._job_repository.save(job)
        return RestartFailedProcessingJobResult(
            campaign=campaign,
            audio_track=audio_track,
            source_job=source_job,
            job=job,
        )
