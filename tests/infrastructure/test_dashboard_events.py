from datetime import datetime

from notekeeper.application import (
    DashboardChangedEvent,
    DashboardRefreshScope,
)
from notekeeper.domain import (
    AudioTrackId,
    Campaign,
    CampaignId,
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
)
from notekeeper.infrastructure.runtime import (
    EventPublishingCampaignRepository,
    EventPublishingJobCleaner,
    EventPublishingJobRepository,
    InMemoryDashboardEventHub,
)


def test_dashboard_event_hub_fans_out_and_unsubscribes() -> None:
    hub = InMemoryDashboardEventHub()
    received: list[DashboardChangedEvent] = []
    unsubscribe = hub.subscribe(received.append)
    event = DashboardChangedEvent(
        campaign_id="campaign-1",
        scope=DashboardRefreshScope.CAMPAIGN_CONTENT,
    )

    hub.publish(event)
    unsubscribe()
    hub.publish(event)

    assert received == [event]


def test_campaign_repository_publishes_scope_after_successful_save() -> None:
    repository = _CampaignRepository()
    events = _CollectingEvents()
    decorated = EventPublishingCampaignRepository(repository, events)
    campaign = Campaign(id=CampaignId("campaign-1"), name="Demo")

    decorated.save(campaign)
    decorated.save(campaign)
    decorated.save(Campaign(id=campaign.id, name="Renamed"))

    assert [event.scope for event in events.items] == [
        DashboardRefreshScope.CAMPAIGN_LIST,
        DashboardRefreshScope.CAMPAIGN_CONTENT,
        DashboardRefreshScope.CAMPAIGN_LIST,
    ]


def test_job_repository_publishes_only_successful_mutations() -> None:
    job = _job(JobStatus.PENDING)
    repository = _JobRepository(job)
    events = _CollectingEvents()
    decorated = EventPublishingJobRepository(repository, events)

    assert decorated.save_if_status(
        _job(JobStatus.RUNNING),
        JobStatus.FAILED,
    ) is False
    assert events.items == []

    assert decorated.save_if_status(
        _job(JobStatus.RUNNING),
        JobStatus.PENDING,
    ) is True
    decorated.delete(job.id)

    assert len(events.items) == 2
    assert all(
        event.campaign_id == "campaign-1"
        and event.scope is DashboardRefreshScope.CAMPAIGN_CONTENT
        for event in events.items
    )


def test_job_cleaner_publishes_once_after_successful_batch() -> None:
    events = _CollectingEvents()
    decorated = EventPublishingJobCleaner(_JobCleaner(), events)
    job = _job(JobStatus.FAILED)

    deleted = decorated.clean(job.campaign_id, (job,))

    assert deleted == (job.id,)
    assert events.items == [
        DashboardChangedEvent(
            campaign_id="campaign-1",
            scope=DashboardRefreshScope.CAMPAIGN_CONTENT,
        ),
    ]


def _job(status: JobStatus) -> ProcessingJob:
    return ProcessingJob(
        id=ProcessingJobId("job-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
        status=status,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )


class _CollectingEvents:
    def __init__(self) -> None:
        self.items: list[DashboardChangedEvent] = []

    def publish(self, event: DashboardChangedEvent) -> None:
        self.items.append(event)


class _CampaignRepository:
    def __init__(self) -> None:
        self.items: dict[CampaignId, Campaign] = {}

    def get(self, campaign_id: CampaignId) -> Campaign | None:
        return self.items.get(campaign_id)

    def list(self) -> tuple[Campaign, ...]:
        return tuple(self.items.values())

    def save(self, campaign: Campaign) -> None:
        self.items[campaign.id] = campaign

    def delete(self, campaign_id: CampaignId) -> None:
        self.items.pop(campaign_id, None)


class _JobRepository:
    def __init__(self, job: ProcessingJob) -> None:
        self.job = job

    def get(self, job_id: ProcessingJobId) -> ProcessingJob | None:
        return self.job if job_id == self.job.id else None

    def list_for_campaign(
        self,
        campaign_id: CampaignId,
    ) -> tuple[ProcessingJob, ...]:
        return (self.job,) if self.job.campaign_id == campaign_id else ()

    def list_for_audio_track(
        self,
        audio_track_id: AudioTrackId,
    ) -> tuple[ProcessingJob, ...]:
        return (self.job,) if self.job.audio_track_id == audio_track_id else ()

    def save(self, job: ProcessingJob) -> None:
        self.job = job

    def save_if_status(
        self,
        job: ProcessingJob,
        expected_status: JobStatus,
    ) -> bool:
        if self.job.status is not expected_status:
            return False
        self.job = job
        return True

    def delete(self, job_id: ProcessingJobId) -> None:
        if self.job.id == job_id:
            self.job = None  # type: ignore[assignment]


class _JobCleaner:
    def clean(
        self,
        campaign_id: CampaignId,
        jobs: tuple[ProcessingJob, ...],
    ) -> tuple[ProcessingJobId, ...]:
        assert all(job.campaign_id == campaign_id for job in jobs)
        return tuple(job.id for job in jobs)
