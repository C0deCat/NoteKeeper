"""List campaign audio tracks use case."""

from notekeeper.application.commands import ListAudioTracksCommand
from notekeeper.application.ports import CampaignRepository
from notekeeper.application.results import ListAudioTracksResult
from notekeeper.application.use_cases.utils import _require_campaign
from notekeeper.domain import CampaignId


class ListAudioTracks:
    def __init__(self, campaign_repository: CampaignRepository) -> None:
        self._campaign_repository = campaign_repository

    def execute(self, command: ListAudioTracksCommand) -> ListAudioTracksResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        return ListAudioTracksResult(audio_tracks=campaign.audio_tracks)
