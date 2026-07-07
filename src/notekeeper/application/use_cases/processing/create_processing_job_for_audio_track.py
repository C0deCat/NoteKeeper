"""Create a processing job for an existing audio track use case."""

from notekeeper.application.commands import CreateProcessingJobForAudioTrackCommand
from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import (
    AudioTrackRepository,
    CampaignRepository,
    Clock,
    IdGenerator,
    JobRepository,
)
from notekeeper.application.results import CreateProcessingJobForAudioTrackResult
from notekeeper.application.use_cases.utils import (
    _require_audio_track,
    _require_campaign,
)
from notekeeper.domain import (
    AudioTrackId,
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
    ensure_campaign_ready_for_processing,
)


class CreateProcessingJobForAudioTrack:
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
        command: CreateProcessingJobForAudioTrackCommand,
    ) -> CreateProcessingJobForAudioTrackResult:
        audio_track = _require_audio_track(
            self._audio_track_repository,
            AudioTrackId(command.audio_track_id),
        )
        campaign = _require_campaign(
            self._campaign_repository,
            audio_track.campaign_id,
        )
        if all(track.id != audio_track.id for track in campaign.audio_tracks):
            raise NotFoundError(
                f"audio track {audio_track.id} was not found in campaign {campaign.id}",
            )

        ensure_campaign_ready_for_processing(campaign)

        now = self._clock.now()
        job = ProcessingJob(
            id=ProcessingJobId(self._id_generator.processing_job_id()),
            campaign_id=campaign.id,
            audio_track_id=audio_track.id,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        self._job_repository.save(job)
        return CreateProcessingJobForAudioTrackResult(
            campaign=campaign,
            audio_track=audio_track,
            job=job,
        )
