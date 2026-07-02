"""Delete campaign audio track use case."""

from notekeeper.application.commands import DeleteAudioTrackCommand
from notekeeper.application.ports import CampaignRepository, JobRepository
from notekeeper.application.results import DeleteAudioTrackResult
from notekeeper.application.use_cases.campaigns.utils import (
    delete_pending_jobs,
    find_audio_track,
)
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId, remove_audio_track


class DeleteAudioTrack:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        job_repository: JobRepository,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._job_repository = job_repository

    def execute(self, command: DeleteAudioTrackCommand) -> DeleteAudioTrackResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        audio_track = find_audio_track(campaign.audio_tracks, command.audio_track_id)
        delete_pending_jobs(self._job_repository, audio_track.id)
        updated_campaign = remove_audio_track(campaign, audio_track.id)
        self._campaign_repository.save(updated_campaign)
        return DeleteAudioTrackResult(
            campaign=updated_campaign,
            audio_track_id=command.audio_track_id,
        )
