import asyncio
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from textual.containers import VerticalScroll
from textual.coordinate import Coordinate
from textual.widgets import Button, DataTable, Input, Select, Static, Switch

from notekeeper.application import (
    ClearFailedJobsForCampaignCommand,
    ClearFailedJobsForCampaignResult,
    CreateProcessingJobForAudioTrackCommand,
    CreateProcessingJobForAudioTrackResult,
    CreateCampaignResult,
    DashboardChangedEvent,
    DashboardRefreshScope,
    DeleteAudioTrackCommand,
    DeleteCampaignResult,
    DeleteParticipantCommand,
    DeleteVoiceSampleCommand,
    GenerateRecapCommand,
    GenerateRecapResult,
    GetCampaignCommand,
    GetCampaignResult,
    GetJobStatusResult,
    InspectAudioMetadataResult,
    InspectLocalAudioFileResult,
    ListAudioTracksResult,
    ListCampaignsResult,
    ListJobsForCampaignResult,
    ListParticipantsResult,
    ListVoiceSamplesResult,
    ManualSpeakerMappingCommand,
    RestartFailedProcessingJobCommand,
    RestartFailedProcessingJobResult,
    RunProcessingJobCommand,
    SyncCampaignFolderCommand,
    SyncCampaignFolderResult,
    UpdateAudioTrackCommand,
    UpdateCampaignResult,
    UpdateParticipantCommand,
)
from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrack,
    Campaign,
    CampaignId,
    JobStatus,
    Participant,
    ParticipantId,
    PipelineWarning,
    PipelineWarningKind,
    ProcessingJob,
    Recap,
    SpeakerLabel,
    VoiceSample,
)
from notekeeper.interfaces import RuntimeDiagnostics, Stage1UseCases
from notekeeper.interfaces.tui import (
    AudioFileExplorerScreen,
    NoteKeeperTui,
    RecordingScreen,
    VoiceSampleScreen,
)
from notekeeper.interfaces.tui.campaign_management_screen import ManageCampaignsScreen
from notekeeper.interfaces.tui.clear_failed_jobs_screen import ClearFailedJobsScreen
from notekeeper.interfaces.tui.identifier_data_table import compact_identifier
from notekeeper.interfaces.tui.job_action_confirmation_screen import (
    JobActionConfirmationScreen,
)
from notekeeper.interfaces.tui.object_action_confirmation_screen import (
    ObjectActionConfirmationScreen,
)
from notekeeper.interfaces.tui.preview_app import MarkdownPreviewScreen
from notekeeper.interfaces.tui.remove_voice_sample_screen import (
    RemoveVoiceSampleScreen,
)
from notekeeper.interfaces.tui.rename_screen import RenameScreen
from notekeeper.interfaces.tui.review_app import ReviewMappingsScreen
from notekeeper.interfaces.tui.tui import DashboardWarning
from notekeeper.infrastructure.runtime import (
    InMemoryDashboardEventHub,
    InMemoryProgressEventHub,
)


class FakeUseCase:
    def __init__(self, result) -> None:
        self.result = result
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        return self.result


def assert_modal_is_centered(screen) -> None:
    modal = screen.query_one(".modal")
    assert abs(2 * modal.region.x + modal.region.width - screen.region.width) <= 1
    assert abs(2 * modal.region.y + modal.region.height - screen.region.height) <= 1


class FakeRestartUseCase(FakeUseCase):
    def __init__(
        self,
        result,
        list_jobs_use_case: FakeUseCase,
        dashboard_events: InMemoryDashboardEventHub,
    ) -> None:
        super().__init__(result)
        self.list_jobs_use_case = list_jobs_use_case
        self.dashboard_events = dashboard_events

    def execute(self, command):
        result = super().execute(command)
        existing_jobs = self.list_jobs_use_case.result.jobs
        self.list_jobs_use_case.result = ListJobsForCampaignResult(
            jobs=(*existing_jobs, result.job),
        )
        self.dashboard_events.publish(
            DashboardChangedEvent(
                campaign_id=str(result.job.campaign_id),
                scope=DashboardRefreshScope.CAMPAIGN_CONTENT,
            ),
        )
        return result


class FakeClearFailedJobsUseCase:
    def __init__(
        self,
        list_jobs_use_case: FakeUseCase,
        dashboard_events: InMemoryDashboardEventHub,
    ) -> None:
        self.list_jobs_use_case = list_jobs_use_case
        self.dashboard_events = dashboard_events
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        jobs = self.list_jobs_use_case.result.jobs
        deleted_job_ids = tuple(
            str(job.id)
            for job in jobs
            if str(job.campaign_id) == command.campaign_id
            and job.status is JobStatus.FAILED
        )
        self.list_jobs_use_case.result = ListJobsForCampaignResult(
            jobs=tuple(
                job
                for job in jobs
                if str(job.id) not in deleted_job_ids
            ),
        )
        self.dashboard_events.publish(
            DashboardChangedEvent(
                campaign_id=command.campaign_id,
                scope=DashboardRefreshScope.CAMPAIGN_CONTENT,
            ),
        )
        return ClearFailedJobsForCampaignResult(
            deleted_job_ids=deleted_job_ids,
        )


class FakeGenerateRecapUseCase(FakeUseCase):
    def __init__(
        self,
        list_jobs_use_case: FakeUseCase,
        dashboard_events: InMemoryDashboardEventHub,
    ) -> None:
        super().__init__(None)
        self.list_jobs_use_case = list_jobs_use_case
        self.dashboard_events = dashboard_events

    def execute(self, command):
        result = super().execute(command)
        self.list_jobs_use_case.result = ListJobsForCampaignResult(
            jobs=tuple(
                result.job if str(job.id) == str(result.job.id) else job
                for job in self.list_jobs_use_case.result.jobs
            ),
        )
        self.dashboard_events.publish(
            DashboardChangedEvent(
                campaign_id=str(result.job.campaign_id),
                scope=DashboardRefreshScope.CAMPAIGN_CONTENT,
            ),
        )
        return result


class FakeJobStatusUseCase:
    def __init__(self, jobs: tuple[ProcessingJob, ...]) -> None:
        self.jobs = {str(job.id): job for job in jobs}
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        return GetJobStatusResult(job=self.jobs[str(command.job_id)])


class FakeCreateCampaignUseCase:
    def __init__(self, list_campaigns_use_case: FakeUseCase) -> None:
        self.list_campaigns_use_case = list_campaigns_use_case
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        campaign = Campaign(
            id=CampaignId(f"campaign-{len(self.list_campaigns_use_case.result.campaigns) + 1}"),
            name=command.name,
        )
        self.list_campaigns_use_case.result = ListCampaignsResult(
            campaigns=(*self.list_campaigns_use_case.result.campaigns, campaign),
        )
        return CreateCampaignResult(campaign=campaign)


class FakeUpdateCampaignUseCase:
    def __init__(self, list_campaigns_use_case: FakeUseCase) -> None:
        self.list_campaigns_use_case = list_campaigns_use_case
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        campaigns = tuple(
            replace(campaign, name=command.name)
            if str(campaign.id) == command.campaign_id
            else campaign
            for campaign in self.list_campaigns_use_case.result.campaigns
        )
        self.list_campaigns_use_case.result = ListCampaignsResult(campaigns=campaigns)
        campaign = next(
            item for item in campaigns if str(item.id) == command.campaign_id
        )
        return UpdateCampaignResult(campaign=campaign)


class FakeDeleteCampaignUseCase:
    def __init__(self, list_campaigns_use_case: FakeUseCase) -> None:
        self.list_campaigns_use_case = list_campaigns_use_case
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        self.list_campaigns_use_case.result = ListCampaignsResult(
            campaigns=tuple(
                campaign
                for campaign in self.list_campaigns_use_case.result.campaigns
                if str(campaign.id) != command.campaign_id
            ),
        )
        return DeleteCampaignResult(campaign_id=command.campaign_id)


class FakeRuntime:
    def __init__(self, *, has_campaigns: bool = True) -> None:
        self.dashboard_events = InMemoryDashboardEventHub()
        self.progress_events = InMemoryProgressEventHub()
        campaign = Campaign(id=CampaignId("campaign-1"), name="Demo")
        participant = Participant(
            id=ParticipantId("participant-1"),
            campaign_id=campaign.id,
            display_name="Alice",
        )
        job = ProcessingJob(
            id="job-1",
            campaign_id=campaign.id,
            audio_track_id="audio-track-1",
            status=JobStatus.PENDING,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
        second_job = ProcessingJob(
            id="job-2",
            campaign_id=campaign.id,
            audio_track_id="audio-track-1",
            status=JobStatus.FAILED,
            created_at=datetime(2026, 1, 2),
            updated_at=datetime(2026, 1, 2),
            error_message="failed",
        )
        restarted_job = ProcessingJob(
            id="job-3",
            campaign_id=campaign.id,
            audio_track_id="audio-track-1",
            status=JobStatus.PENDING,
            created_at=datetime(2026, 1, 3),
            updated_at=datetime(2026, 1, 3),
        )
        campaigns = (campaign,) if has_campaigns else ()
        participants = (participant,) if has_campaigns else ()
        jobs = (job, second_job) if has_campaigns else ()
        metadata = AudioMetadata(
            duration_seconds=12,
            format="wav",
            file_size_bytes=100,
        )
        audio_track = AudioTrack(
            id="audio-track-1",
            campaign_id=campaign.id,
            artifact=ArtifactRef(
                uri="campaign-1/records/normalized/audio-track-1.wav",
            ),
            metadata=metadata,
            title="Session 1",
        )
        dashboard_campaign = replace(
            campaign,
            participants=participants,
            audio_tracks=(audio_track,) if has_campaigns else (),
        )
        list_campaigns = FakeUseCase(ListCampaignsResult(campaigns=campaigns))
        list_jobs = FakeUseCase(ListJobsForCampaignResult(jobs=jobs))
        self.use_cases = Stage1UseCases(
            create_campaign=FakeCreateCampaignUseCase(list_campaigns),
            get_campaign=FakeUseCase(
                GetCampaignResult(campaign=dashboard_campaign),
            ),
            list_campaigns=list_campaigns,
            update_campaign=FakeUpdateCampaignUseCase(list_campaigns),
            delete_campaign=FakeDeleteCampaignUseCase(list_campaigns),
            add_participant=FakeUseCase(None),
            list_participants=FakeUseCase(
                ListParticipantsResult(participants=participants),
            ),
            update_participant=FakeUseCase(None),
            delete_participant=FakeUseCase(None),
            add_voice_sample=FakeUseCase(None),
            list_voice_samples=FakeUseCase(ListVoiceSamplesResult(voice_samples=())),
            delete_voice_sample=FakeUseCase(None),
            register_audio_track=FakeUseCase(None),
            list_audio_tracks=FakeUseCase(
                ListAudioTracksResult(
                    audio_tracks=(audio_track,) if has_campaigns else (),
                ),
            ),
            update_audio_track=FakeUseCase(None),
            delete_audio_track=FakeUseCase(None),
            create_processing_job_for_audio_track=FakeUseCase(
                CreateProcessingJobForAudioTrackResult(
                    campaign=campaign,
                    audio_track=audio_track,
                    job=job,
                ),
            ),
            submit_recording_for_processing=FakeUseCase(None),
            run_processing_job=FakeUseCase(GetJobStatusResult(job=job)),
            restart_failed_processing_job=FakeRestartUseCase(
                RestartFailedProcessingJobResult(
                    campaign=campaign,
                    audio_track=audio_track,
                    source_job=second_job,
                    job=restarted_job,
                ),
                list_jobs,
                self.dashboard_events,
            ),
            clear_failed_jobs_for_campaign=FakeClearFailedJobsUseCase(
                list_jobs,
                self.dashboard_events,
            ),
            list_jobs_for_campaign=list_jobs,
            get_job_status=FakeJobStatusUseCase((job, second_job, restarted_job)),
            review_speaker_mappings=FakeUseCase(GetJobStatusResult(job=job)),
            generate_recap=FakeGenerateRecapUseCase(
                list_jobs,
                self.dashboard_events,
            ),
            export_transcript_markdown=FakeUseCase(None),
            export_recap_markdown=FakeUseCase(None),
            preview_transcript_markdown=FakeUseCase(None),
            preview_recap_markdown=FakeUseCase(None),
            inspect_audio_metadata=FakeUseCase(
                InspectAudioMetadataResult(
                    artifact=ArtifactRef(uri="session.wav"),
                    metadata=metadata,
                ),
            ),
            inspect_local_audio_file=FakeUseCase(
                InspectLocalAudioFileResult(
                    source_path=str(Path("session.wav").resolve()),
                    metadata=metadata,
                ),
            ),
            sync_campaign_folder=FakeUseCase(
                SyncCampaignFolderResult(
                    campaign=campaign,
                    participants_created=1,
                    voice_samples_added=2,
                    audio_tracks_added=3,
                ),
            ),
        )

    def diagnostics(self, campaign_id: str | None = None) -> RuntimeDiagnostics:
        return RuntimeDiagnostics(
            storage_root="artifacts",
            sqlite_path="notekeeper.sqlite3",
            processing_work_root="work",
            recap_prompts_file="recap_prompts.json",
            whisperx_model_name="small",
            whisperx_device="cpu",
            whisperx_compute_type="int8",
            whisperx_vad_method="silero",
            deepseek_configured=True,
            huggingface_configured=True,
            recent_messages=("job-1: warning",),
        )

    def format_artifact_location(self, artifact: ArtifactRef) -> str:
        return artifact.uri


def test_tui_dashboard_loads_campaign_data() -> None:
    async def run() -> None:
        app = NoteKeeperTui(FakeRuntime())
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#jobs-table", DataTable).row_count == 2
            assert app.query_one("#players-table", DataTable).row_count == 1
            assert isinstance(app._selected_object, ProcessingJob)
            assert str(app._selected_object.id) == "job-2"
            recordings_table = app.query_one("#recordings-table", DataTable)
            recording_row = recordings_table.get_row_at(0)
            assert recording_row[3] == "2"
            assert recording_row[4] == "failed"
            assert app.query_one("#jobs-table", DataTable).show_cursor is True
            assert recordings_table.show_cursor is False
            assert app.query_one("#players-table", DataTable).show_cursor is False
            assert app.query_one("#warnings-table", DataTable).show_cursor is False

    asyncio.run(run())


def test_tui_dashboard_refreshes_from_events_without_overwriting_status() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        pending, failed = runtime.use_cases.list_jobs_for_campaign.result.jobs
        waiting = replace(
            failed,
            status=JobStatus.WAITING_FOR_REVIEW,
            error_message=None,
        )
        runtime.use_cases.list_jobs_for_campaign.result = ListJobsForCampaignResult(
            jobs=(pending, waiting),
        )
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._set_status("Processing")
            jobs_table = app.query_one("#jobs-table", DataTable)
            for status in (
                JobStatus.RUNNING,
                JobStatus.WAITING_FOR_REVIEW,
                JobStatus.RUNNING,
            ):
                updated = replace(waiting, status=status)
                runtime.use_cases.list_jobs_for_campaign.result = (
                    ListJobsForCampaignResult(jobs=(pending, updated))
                )
                runtime.dashboard_events.publish(
                    DashboardChangedEvent(
                        campaign_id="campaign-1",
                        scope=DashboardRefreshScope.CAMPAIGN_CONTENT,
                    ),
                )
                await pilot.pause()
                await pilot.pause()
                assert jobs_table.get_row_at(0)[1] == status.value
                assert isinstance(app._selected_object, ProcessingJob)
                assert app._selected_object.status is status
            assert "Processing" in str(app.query_one("#status", Static).render())

            completed = replace(waiting, status=JobStatus.COMPLETED)
            runtime.use_cases.list_jobs_for_campaign.result = (
                ListJobsForCampaignResult(jobs=(pending, completed))
            )
            runtime.dashboard_events.publish(
                DashboardChangedEvent(
                    campaign_id="campaign-2",
                    scope=DashboardRefreshScope.CAMPAIGN_CONTENT,
                ),
            )
            await pilot.pause()
            assert jobs_table.get_row_at(0)[1] == JobStatus.RUNNING.value

            campaign_reads = len(runtime.use_cases.list_campaigns.commands)
            runtime.dashboard_events.publish(
                DashboardChangedEvent(
                    campaign_id="campaign-2",
                    scope=DashboardRefreshScope.CAMPAIGN_LIST,
                ),
            )
            await pilot.pause()
            await pilot.pause()
            assert len(runtime.use_cases.list_campaigns.commands) > campaign_reads
            assert jobs_table.get_row_at(0)[1] == JobStatus.COMPLETED.value

    asyncio.run(run())


def test_tui_compacts_identifier_cells_and_shows_full_hover_tooltips() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        jobs = runtime.use_cases.list_jobs_for_campaign.result.jobs
        job_with_transcript = replace(
            jobs[0],
            transcript_id="transcript-123456789",
        )
        job_with_recap = replace(jobs[1], recap_id="recap-987654321")
        runtime.use_cases.list_jobs_for_campaign.result = ListJobsForCampaignResult(
            jobs=(job_with_transcript, job_with_recap),
        )

        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            jobs_table = app.query_one("#jobs-table", DataTable)
            recordings_table = app.query_one("#recordings-table", DataTable)
            players_table = app.query_one("#players-table", DataTable)
            warnings_table = app.query_one("#warnings-table", DataTable)

            assert jobs_table.get_row_at(0)[0] == compact_identifier("job-2")
            assert jobs_table.get_row_at(0)[3] == compact_identifier("recap-987654321")
            assert jobs_table.get_row_at(1)[2] == compact_identifier(
                "transcript-123456789",
            )
            assert recordings_table.get_row_at(0)[0] == compact_identifier(
                "audio-track-1",
            )
            assert players_table.get_row_at(0)[0] == compact_identifier(
                "participant-1",
            )
            assert warnings_table.get_row_at(0)[0] == compact_identifier("job-2")

            jobs_table.hover_coordinate = Coordinate(1, 2)
            await pilot.pause()
            assert jobs_table.tooltip == "transcript-123456789"

            jobs_table.hover_coordinate = Coordinate(1, 1)
            await pilot.pause()
            assert jobs_table.tooltip is None

    asyncio.run(run())


def test_tui_sorts_dashboard_rows_newest_first() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        campaign = runtime.use_cases.list_campaigns.result.campaigns[0]
        metadata = AudioMetadata(duration_seconds=30, format="wav")
        second_track = AudioTrack(
            id="audio-track-2",
            campaign_id=campaign.id,
            artifact=ArtifactRef(
                uri="campaign-1/records/normalized/audio-track-2.wav",
            ),
            metadata=metadata,
            title="Session 2",
        )
        second_participant = Participant(
            id="participant-2",
            campaign_id=campaign.id,
            display_name="Bob",
        )
        jobs = runtime.use_cases.list_jobs_for_campaign.result.jobs
        older_job = replace(
            jobs[0],
            warnings=(
                PipelineWarning(PipelineWarningKind.UNCERTAIN_MAPPING, "older warning"),
            ),
        )
        newer_job = replace(
            jobs[1],
            warnings=(
                PipelineWarning(PipelineWarningKind.UNKNOWN_PARTICIPANT, "newer warning"),
            ),
        )
        runtime.use_cases.list_audio_tracks.result = ListAudioTracksResult(
            audio_tracks=(*runtime.use_cases.list_audio_tracks.result.audio_tracks, second_track),
        )
        runtime.use_cases.list_participants.result = ListParticipantsResult(
            participants=(
                *runtime.use_cases.list_participants.result.participants,
                second_participant,
            ),
        )
        runtime.use_cases.get_campaign.result = GetCampaignResult(
            campaign=replace(
                runtime.use_cases.get_campaign.result.campaign,
                audio_tracks=runtime.use_cases.list_audio_tracks.result.audio_tracks,
                participants=runtime.use_cases.list_participants.result.participants,
            ),
        )
        runtime.use_cases.list_jobs_for_campaign.result = ListJobsForCampaignResult(
            jobs=(older_job, newer_job),
        )

        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            jobs_table = app.query_one("#jobs-table", DataTable)
            recordings_table = app.query_one("#recordings-table", DataTable)
            players_table = app.query_one("#players-table", DataTable)
            warnings_table = app.query_one("#warnings-table", DataTable)

            assert isinstance(app._selected_object, ProcessingJob)
            assert str(app._selected_object.id) == "job-2"
            assert jobs_table.get_row_at(0)[0] == compact_identifier("job-2")
            assert recordings_table.get_row_at(0)[0] == compact_identifier(
                "audio-track-2",
            )
            assert players_table.get_row_at(0)[0] == compact_identifier(
                "participant-2",
            )
            assert warnings_table.get_row_at(0)[2] == "newer warning"
            assert warnings_table.get_row_at(1)[1] == "error"
            assert warnings_table.get_row_at(2)[2] == "older warning"

    asyncio.run(run())


def test_tui_action_buttons_follow_current_dashboard_context() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()

            assert app.query_one("#refresh", Button).disabled is False
            assert app.query_one("#manage-campaign", Button).disabled is False
            assert app.query_one("#diagnostics", Button).disabled is False
            assert app.query_one("#sync-folder", Button).disabled is False
            assert app.query_one("#add-player", Button).disabled is False
            assert app.query_one("#add-sample", Button).disabled is False
            assert app.query_one("#submit-recording", Button).disabled is True
            assert app.query_one("#create-job", Button).display is False
            action_button = app.query_one("#job-action", Button)
            assert action_button.display is True
            assert action_button.disabled is True
            assert str(action_button.label) == "Restart"
            assert action_button.variant == "success"
            assert app.query_one("#clear-failed-jobs", Button).disabled is False
            recreate_button = app.query_one("#recreate-recap", Button)
            assert recreate_button.display is True
            assert recreate_button.disabled is True

            jobs_table = app.query_one("#jobs-table", DataTable)
            app._select_table_row(jobs_table, "job-1")
            await pilot.pause()
            assert isinstance(app._selected_object, ProcessingJob)
            assert str(app._selected_object.id) == "job-1"
            assert action_button.disabled is False
            assert str(action_button.label) == "Run"

            campaign = runtime.use_cases.list_campaigns.result.campaigns[0]
            participant = runtime.use_cases.list_participants.result.participants[0]
            metadata = AudioMetadata(duration_seconds=12, format="wav")
            runtime.use_cases.list_voice_samples.result = ListVoiceSamplesResult(
                voice_samples=(
                    VoiceSample(
                        id="voice-sample-1",
                        campaign_id=campaign.id,
                        participant_id=participant.id,
                        artifact=ArtifactRef(uri="players/alice.wav"),
                        metadata=metadata,
                    ),
                ),
            )
            runtime.use_cases.get_campaign.result = GetCampaignResult(
                campaign=replace(
                    runtime.use_cases.get_campaign.result.campaign,
                    voice_samples=runtime.use_cases.list_voice_samples.result.voice_samples,
                ),
            )
            app.refresh_dashboard(update_campaigns=False)
            assert app.query_one("#submit-recording", Button).disabled is False
            recordings_table = app.query_one("#recordings-table", DataTable)
            app._select_table_row(recordings_table, "audio-track-1")
            await pilot.pause()
            assert app.query_one("#create-job", Button).display is True
            assert app.query_one("#create-job", Button).disabled is False
            assert action_button.display is False
            assert recreate_button.display is False

            jobs_table = app.query_one("#jobs-table", DataTable)
            app._select_table_row(jobs_table, "job-2")
            await pilot.pause()
            assert action_button.display is True
            assert action_button.disabled is False
            assert str(action_button.label) == "Restart"

            waiting_job = replace(
                runtime.use_cases.list_jobs_for_campaign.result.jobs[1],
                status=JobStatus.WAITING_FOR_REVIEW,
                transcript_id="transcript-1",
                error_message=None,
            )
            pending_job = runtime.use_cases.list_jobs_for_campaign.result.jobs[0]
            runtime.use_cases.list_jobs_for_campaign.result = ListJobsForCampaignResult(
                jobs=(pending_job, waiting_job),
            )
            app._selected_object = waiting_job
            app.refresh_dashboard(update_campaigns=False)
            assert action_button.display is True
            assert action_button.disabled is False
            assert str(action_button.label) == "Review and Continue"
            assert app.query_one("#preview-transcript", Button).disabled is False
            assert app.query_one("#export-transcript", Button).disabled is False
            assert app.query_one("#preview-recap", Button).disabled is True
            assert recreate_button.display is True
            assert recreate_button.disabled is False

            app._recap_generation_in_progress = True
            app._update_action_buttons()
            assert recreate_button.disabled is True
            app._recap_generation_in_progress = False
            app._update_action_buttons()
            assert recreate_button.disabled is False

            completed_job = replace(
                waiting_job,
                status=JobStatus.COMPLETED,
                recap_id="recap-1",
            )
            runtime.use_cases.list_jobs_for_campaign.result = ListJobsForCampaignResult(
                jobs=(pending_job, completed_job),
            )
            app.refresh_dashboard(update_campaigns=False)
            assert action_button.display is False
            assert app.query_one("#preview-recap", Button).disabled is False
            assert app.query_one("#export-recap", Button).disabled is False

    asyncio.run(run())


def test_tui_recreate_recap_runs_worker_and_refreshes_selected_job() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        pending_job, failed_job = runtime.use_cases.list_jobs_for_campaign.result.jobs
        job_with_transcript = replace(
            failed_job,
            status=JobStatus.COMPLETED,
            transcript_id="transcript-1",
            recap_id="recap-old",
            error_message=None,
        )
        runtime.use_cases.list_jobs_for_campaign.result = ListJobsForCampaignResult(
            jobs=(pending_job, job_with_transcript),
        )
        new_recap = Recap(
            id="recap-new",
            transcript_id="transcript-1",
            markdown="# New recap",
        )
        updated_job = replace(job_with_transcript, recap_id=new_recap.id)
        runtime.use_cases.generate_recap.result = GenerateRecapResult(
            job=updated_job,
            recap=new_recap,
        )
        app = NoteKeeperTui(runtime)

        async with app.run_test() as pilot:
            await pilot.pause()
            recreate_button = app.query_one("#recreate-recap", Button)
            assert recreate_button.display is True
            assert recreate_button.disabled is False

            await pilot.click("#recreate-recap")
            await pilot.pause()

            command = runtime.use_cases.generate_recap.commands[-1]
            assert isinstance(command, GenerateRecapCommand)
            assert command.job_id == "job-2"
            assert isinstance(app._selected_object, ProcessingJob)
            assert app._selected_object.recap_id == new_recap.id
            assert app.query_one("#jobs-table", DataTable).get_row_at(0)[3] == (
                compact_identifier("recap-new")
            )
            assert "Recreated recap recap-new" in str(
                app.query_one("#status", Static).render(),
            )
            assert app._recap_generation_in_progress is False

    asyncio.run(run())


def test_tui_job_delete_and_cancel_buttons_follow_job_status() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#delete-job", Button).disabled is False
            assert app.query_one("#cancel-job", Button).disabled is True

            failed = app._selected_object
            assert isinstance(failed, ProcessingJob)
            running = replace(failed, status=JobStatus.RUNNING)
            runtime.use_cases.list_jobs_for_campaign.result = ListJobsForCampaignResult(
                jobs=(running,),
            )
            app.refresh_dashboard(update_campaigns=False)
            await pilot.pause()
            assert app.query_one("#delete-job", Button).disabled is True
            assert app.query_one("#cancel-job", Button).disabled is False

            app._review_job_id = str(running.id)
            app._update_action_buttons()
            assert app.query_one("#cancel-job", Button).disabled is True

    asyncio.run(run())


def test_tui_delete_job_opens_preserving_confirmation() -> None:
    async def run() -> None:
        app = NoteKeeperTui(FakeRuntime())
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#delete-job")
            await pilot.pause()
            assert isinstance(app.screen, JobActionConfirmationScreen)
            text = " ".join(
                str(label.render()) for label in app.screen.query("Label")
            )
            assert "Transcripts and recaps will be preserved" in text
            await pilot.click("#back")

    asyncio.run(run())


def test_tui_dashboard_uses_one_campaign_aggregate_read() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert len(runtime.use_cases.get_campaign.commands) == 1
            command = runtime.use_cases.get_campaign.commands[0]
            assert isinstance(command, GetCampaignCommand)
            assert command.campaign_id == "campaign-1"
            assert not runtime.use_cases.list_participants.commands
            assert not runtime.use_cases.list_voice_samples.commands
            assert not runtime.use_cases.list_audio_tracks.commands

            campaign_list_reads = len(runtime.use_cases.list_campaigns.commands)
            app.refresh_dashboard(update_campaigns=False)
            assert len(runtime.use_cases.get_campaign.commands) == 2
            assert len(runtime.use_cases.list_campaigns.commands) == campaign_list_reads

    asyncio.run(run())


def test_tui_players_and_warnings_are_selectable_without_object_actions() -> None:
    async def run() -> None:
        app = NoteKeeperTui(FakeRuntime())
        async with app.run_test(size=(160, 80)) as pilot:
            await pilot.pause()
            tables = {
                table.id: table
                for table in app.query(DataTable)
                if table.id in {
                    "jobs-table",
                    "recordings-table",
                    "players-table",
                    "warnings-table",
                }
            }
            object_button_ids = (
                "create-job",
                "job-action",
                "recreate-recap",
                "preview-transcript",
                "preview-recap",
                "export-transcript",
                "export-recap",
            )

            await pilot.click("#recordings-table", offset=(4, 2))
            await pilot.pause()
            assert isinstance(app._selected_object, AudioTrack)
            assert str(app._selected_object.id) == "audio-track-1"
            assert tables["recordings-table"].show_cursor is True
            assert sum(table.show_cursor for table in tables.values()) == 1
            assert app.query_one("#create-job", Button).display is True

            await pilot.click("#players-table", offset=(4, 2))
            await pilot.pause()
            assert isinstance(app._selected_object, Participant)
            assert str(app._selected_object.id) == "participant-1"
            assert tables["players-table"].show_cursor is True
            assert sum(table.show_cursor for table in tables.values()) == 1
            assert all(
                app.query_one(f"#{button_id}", Button).display is False
                for button_id in object_button_ids
            )

            await pilot.click("#warnings-table", offset=(4, 2))
            await pilot.pause()
            assert isinstance(app._selected_object, DashboardWarning)
            assert app._selected_object.job_id == "job-2"
            assert app._selected_object.kind == "error"
            assert tables["warnings-table"].show_cursor is True
            assert sum(table.show_cursor for table in tables.values()) == 1
            assert all(
                app.query_one(f"#{button_id}", Button).display is False
                for button_id in object_button_ids
            )

            await pilot.click("#jobs-table", offset=(4, 2))
            await pilot.pause()
            assert isinstance(app._selected_object, ProcessingJob)
            assert str(app._selected_object.id) == "job-2"
            assert tables["jobs-table"].show_cursor is True
            assert sum(table.show_cursor for table in tables.values()) == 1

            await pilot.click("#recordings-table", offset=(4, 2))
            await pilot.pause()
            stale_event = DataTable.RowHighlighted(
                tables["jobs-table"],
                0,
                "job-2",
            )
            app.on_data_table_row_highlighted(stale_event)
            assert isinstance(app._selected_object, AudioTrack)

            await pilot.click("#warnings-table", offset=(4, 2))
            await pilot.pause()
            app.refresh_dashboard(update_campaigns=False)
            assert isinstance(app._selected_object, DashboardWarning)
            assert app._selected_object.key == "job-2:error"
            assert tables["warnings-table"].show_cursor is True
            assert sum(table.show_cursor for table in tables.values()) == 1

    asyncio.run(run())


def test_tui_recording_and_player_actions_follow_selection_and_sample_state() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test(size=(160, 80)) as pilot:
            await pilot.pause()
            recording_action_ids = ("rename-recording", "remove-recording")
            player_action_ids = (
                "rename-player",
                "remove-player",
                "remove-voice-sample",
            )
            assert all(
                app.query_one(f"#{button_id}", Button).display is False
                for button_id in (*recording_action_ids, *player_action_ids)
            )

            app._select_table_row(
                app.query_one("#recordings-table", DataTable),
                "audio-track-1",
            )
            assert all(
                app.query_one(f"#{button_id}", Button).display is True
                for button_id in recording_action_ids
            )
            assert all(
                app.query_one(f"#{button_id}", Button).display is False
                for button_id in player_action_ids
            )

            app._select_table_row(
                app.query_one("#players-table", DataTable),
                "participant-1",
            )
            assert all(
                app.query_one(f"#{button_id}", Button).display is True
                for button_id in player_action_ids
            )
            assert app.query_one("#remove-voice-sample", Button).disabled is True

            campaign = runtime.use_cases.get_campaign.result.campaign
            sample = VoiceSample(
                id="sample-1",
                campaign_id=campaign.id,
                participant_id="participant-1",
                artifact=ArtifactRef(uri="players/Alice/sample.wav"),
                metadata=AudioMetadata(duration_seconds=10, format="wav"),
            )
            runtime.use_cases.get_campaign.result = GetCampaignResult(
                campaign=replace(campaign, voice_samples=(sample,)),
            )
            app.refresh_dashboard(update_campaigns=False)
            assert isinstance(app._selected_object, Participant)
            assert app.query_one("#remove-voice-sample", Button).disabled is False

    asyncio.run(run())


def test_tui_rename_recording_and_player_use_existing_update_use_cases() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test(size=(160, 80)) as pilot:
            await pilot.pause()
            app._select_table_row(
                app.query_one("#recordings-table", DataTable),
                "audio-track-1",
            )
            await pilot.pause()
            await pilot.click("#rename-recording")
            await pilot.pause()
            assert isinstance(app.screen, RenameScreen)
            name_input = app.screen.query_one("#new-name", Input)
            assert name_input.value == "Session 1"
            name_input.value = "Renamed Session"
            await pilot.click("#rename")
            await pilot.pause()

            recording_command = runtime.use_cases.update_audio_track.commands[-1]
            assert isinstance(recording_command, UpdateAudioTrackCommand)
            assert recording_command.campaign_id == "campaign-1"
            assert recording_command.audio_track_id == "audio-track-1"
            assert recording_command.artifact_uri == (
                "campaign-1/records/normalized/audio-track-1.wav"
            )
            assert recording_command.artifact_kind == "file"
            assert recording_command.title == "Renamed Session"
            assert isinstance(app._selected_object, AudioTrack)

            app._select_table_row(
                app.query_one("#players-table", DataTable),
                "participant-1",
            )
            await pilot.pause()
            await pilot.click("#rename-player")
            await pilot.pause()
            assert isinstance(app.screen, RenameScreen)
            name_input = app.screen.query_one("#new-name", Input)
            assert name_input.value == "Alice"
            name_input.value = "Alicia"
            await pilot.click("#rename")
            await pilot.pause()

            participant_command = runtime.use_cases.update_participant.commands[-1]
            assert isinstance(participant_command, UpdateParticipantCommand)
            assert participant_command.campaign_id == "campaign-1"
            assert participant_command.participant_id == "participant-1"
            assert participant_command.display_name == "Alicia"
            assert isinstance(app._selected_object, Participant)

    asyncio.run(run())


def test_tui_remove_recording_and_player_require_confirmation() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test(size=(160, 80)) as pilot:
            await pilot.pause()
            app._select_table_row(
                app.query_one("#recordings-table", DataTable),
                "audio-track-1",
            )
            await pilot.pause()
            await pilot.click("#remove-recording")
            await pilot.pause()
            assert isinstance(app.screen, ObjectActionConfirmationScreen)
            await pilot.click("#back")
            await pilot.pause()
            assert runtime.use_cases.delete_audio_track.commands == []

            await pilot.click("#remove-recording")
            await pilot.pause()
            campaign = runtime.use_cases.get_campaign.result.campaign
            runtime.use_cases.get_campaign.result = GetCampaignResult(
                campaign=replace(campaign, audio_tracks=()),
            )
            await pilot.click("#confirm")
            await pilot.pause()
            recording_command = runtime.use_cases.delete_audio_track.commands[-1]
            assert isinstance(recording_command, DeleteAudioTrackCommand)
            assert recording_command.audio_track_id == "audio-track-1"
            assert isinstance(app._selected_object, ProcessingJob)

            campaign = runtime.use_cases.get_campaign.result.campaign
            app._select_table_row(
                app.query_one("#players-table", DataTable),
                "participant-1",
            )
            await pilot.pause()
            await pilot.click("#remove-player")
            await pilot.pause()
            assert isinstance(app.screen, ObjectActionConfirmationScreen)
            modal_text = " ".join(
                str(label.render()) for label in app.screen.query("Label")
            )
            assert "voice samples" in modal_text
            runtime.use_cases.get_campaign.result = GetCampaignResult(
                campaign=replace(campaign, participants=()),
            )
            await pilot.click("#confirm")
            await pilot.pause()
            participant_command = runtime.use_cases.delete_participant.commands[-1]
            assert isinstance(participant_command, DeleteParticipantCommand)
            assert participant_command.participant_id == "participant-1"
            assert isinstance(app._selected_object, ProcessingJob)

    asyncio.run(run())


def test_tui_remove_voice_sample_selects_one_sample_and_keeps_player_selected() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        campaign = runtime.use_cases.get_campaign.result.campaign
        samples = tuple(
            VoiceSample(
                id=f"sample-{index}",
                campaign_id=campaign.id,
                participant_id="participant-1",
                artifact=ArtifactRef(uri=f"players/Alice/sample-{index}.wav"),
                metadata=AudioMetadata(duration_seconds=10, format="wav"),
            )
            for index in (1, 2)
        )
        runtime.use_cases.get_campaign.result = GetCampaignResult(
            campaign=replace(campaign, voice_samples=samples),
        )
        runtime.use_cases.list_voice_samples.result = ListVoiceSamplesResult(
            voice_samples=samples,
        )
        app = NoteKeeperTui(runtime)
        async with app.run_test(size=(160, 80)) as pilot:
            await pilot.pause()
            app._select_table_row(
                app.query_one("#players-table", DataTable),
                "participant-1",
            )
            await pilot.pause()
            await pilot.click("#remove-voice-sample")
            await pilot.pause()
            assert isinstance(app.screen, RemoveVoiceSampleScreen)
            list_command = runtime.use_cases.list_voice_samples.commands[-1]
            assert list_command.campaign_id == "campaign-1"
            assert list_command.participant_id == "participant-1"

            sample_select = app.screen.query_one("#voice-sample", Select)
            sample_select.value = "sample-2"
            await pilot.pause()
            await pilot.click("#remove")
            await pilot.pause()
            delete_command = runtime.use_cases.delete_voice_sample.commands[-1]
            assert isinstance(delete_command, DeleteVoiceSampleCommand)
            assert delete_command.campaign_id == "campaign-1"
            assert delete_command.voice_sample_id == "sample-2"
            assert isinstance(app._selected_object, Participant)
            assert str(app._selected_object.id) == "participant-1"

    asyncio.run(run())


def test_tui_row_highlight_events_stop_when_idle() -> None:
    async def run() -> None:
        highlighted_events: list[str | None] = []

        def record_message(message) -> None:
            if isinstance(message, DataTable.RowHighlighted):
                highlighted_events.append(message.data_table.id)

        app = NoteKeeperTui(FakeRuntime())
        async with app.run_test(
            size=(160, 80),
            message_hook=record_message,
        ) as pilot:
            await pilot.pause(0.2)
            event_count = len(highlighted_events)
            await pilot.pause(0.2)
            assert len(highlighted_events) == event_count

            await pilot.click("#recordings-table", offset=(4, 2))
            await pilot.pause(0.2)
            event_count = len(highlighted_events)
            await pilot.pause(0.2)
            assert len(highlighted_events) == event_count

    asyncio.run(run())


def test_tui_selection_falls_back_to_job_then_recording() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._select_table_row(
                app.query_one("#players-table", DataTable),
                "participant-1",
            )

            runtime.use_cases.list_participants.result = ListParticipantsResult(
                participants=(),
            )
            runtime.use_cases.get_campaign.result = GetCampaignResult(
                campaign=replace(
                    runtime.use_cases.get_campaign.result.campaign,
                    participants=(),
                ),
            )
            app.refresh_dashboard(update_campaigns=False)
            assert isinstance(app._selected_object, ProcessingJob)
            assert str(app._selected_object.id) == "job-2"

            runtime.use_cases.list_jobs_for_campaign.result = ListJobsForCampaignResult(
                jobs=(),
            )
            app.refresh_dashboard(update_campaigns=False)
            assert isinstance(app._selected_object, AudioTrack)
            assert str(app._selected_object.id) == "audio-track-1"
            assert app.query_one("#recordings-table", DataTable).show_cursor is True

    asyncio.run(run())


def test_tui_campaign_actions_wrap_by_available_width() -> None:
    async def run() -> None:
        narrow_app = NoteKeeperTui(FakeRuntime())
        async with narrow_app.run_test(size=(45, 30)) as pilot:
            await pilot.pause()
            panel = narrow_app.query_one("#campaign-actions")
            topbar = narrow_app.query_one("#topbar")
            buttons = tuple(panel.query(Button))
            assert panel.layout.grid_size == (2, 3)
            assert panel.region.y - topbar.region.bottom == 1
            assert len({button.region.y for button in buttons}) == 3
            assert narrow_app.query_one("#refresh", Button).region.width < (
                narrow_app.query_one("#add-sample", Button).region.width
            )
            assert narrow_app.query_one("#refresh", Button).parent is panel
            assert narrow_app.query_one("#diagnostics", Button).parent is panel

        wide_app = NoteKeeperTui(FakeRuntime())
        async with wide_app.run_test(size=(140, 30)) as pilot:
            await pilot.pause()
            panel = wide_app.query_one("#campaign-actions")
            buttons = tuple(panel.query(Button))
            assert panel.layout.grid_size == (6, 1)
            assert len({button.region.y for button in buttons}) == 1
            assert sum(button.region.width for button in buttons) < panel.region.width

    asyncio.run(run())


def test_tui_manages_campaigns_in_a_modal() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not list(app.query("#new-campaign"))

            await pilot.click("#manage-campaign")
            await pilot.pause()
            assert isinstance(app.screen, ManageCampaignsScreen)
            screen = app.screen
            campaigns_table = screen.query_one("#campaigns-table", DataTable)
            assert campaigns_table.get_row_at(0)[0] == compact_identifier("campaign-1")

            campaigns_table.hover_coordinate = Coordinate(0, 0)
            await pilot.pause()
            assert campaigns_table.tooltip == "campaign-1"

            name_input = screen.query_one("#campaign-name", Input)
            name_input.value = "New Campaign"
            await pilot.pause()
            assert screen.query_one("#create", Button).disabled is False
            screen.query_one("#create", Button).press()
            await pilot.pause()
            assert runtime.use_cases.create_campaign.commands[-1].name == "New Campaign"
            assert campaigns_table.row_count == 2
            assert screen._selected_campaign_id == "campaign-2"

            name_input.value = "Renamed Campaign"
            await pilot.pause()
            screen.query_one("#rename", Button).press()
            await pilot.pause()
            assert runtime.use_cases.update_campaign.commands[-1].name == "Renamed Campaign"
            assert screen.query_one("#campaigns-table", DataTable).get_row_at(1)[1] == (
                "Renamed Campaign"
            )

            screen.query_one("#delete", Button).press()
            await pilot.pause()
            app.screen.query_one("#database-only", Button).press()
            await pilot.pause()
            assert runtime.use_cases.delete_campaign.commands[-1].delete_files is False
            assert screen.query_one("#campaigns-table", DataTable).row_count == 1

            screen.query_one("#delete", Button).press()
            await pilot.pause()
            app.screen.query_one("#campaign-and-files", Button).press()
            await pilot.pause()
            assert runtime.use_cases.delete_campaign.commands[-1].delete_files is True
            assert screen.query_one("#campaigns-table", DataTable).row_count == 0

            screen.query_one("#close", Button).press()
            await pilot.pause()
            assert app._selected_campaign_id is None
            assert "No campaign" in str(app.query_one("#status", Static).render())

    asyncio.run(run())


def test_tui_dashboard_loads_without_campaigns() -> None:
    async def run() -> None:
        app = NoteKeeperTui(FakeRuntime(has_campaigns=False))
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#jobs-table", DataTable).row_count == 0
            assert app.query_one("#players-table", DataTable).row_count == 0
            assert "No campaign" in str(app.query_one("#status", Static).render())
            assert app.query_one("#manage-campaign", Button).disabled is False
            assert app.query_one("#sync-folder", Button).disabled is True
            assert app.query_one("#add-player", Button).disabled is True
            assert app.query_one("#add-sample", Button).disabled is True
            assert app.query_one("#submit-recording", Button).disabled is True
            assert app.query_one("#create-job", Button).display is False
            assert app.query_one("#job-action", Button).display is False
            assert app.query_one("#clear-failed-jobs", Button).disabled is True
            assert app.query_one("#recreate-recap", Button).display is False
            assert app.query_one("#preview-transcript", Button).display is False
            assert app.query_one("#export-transcript", Button).display is False
            assert app.query_one("#preview-recap", Button).display is False
            assert app.query_one("#export-recap", Button).display is False

    asyncio.run(run())


def test_tui_dashboard_and_content_are_scrollable() -> None:
    async def run() -> None:
        app = NoteKeeperTui(FakeRuntime())
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#dashboard").styles.overflow_y == "auto"
            assert app.query_one("#actions").styles.overflow_y == "auto"
            assert app.query_one("#content").styles.overflow_y == "auto"

    asyncio.run(run())


def test_tui_markdown_previews_are_scrollable_and_centered() -> None:
    async def run() -> None:
        app = NoteKeeperTui(FakeRuntime())
        async with app.run_test(size=(100, 40)) as pilot:
            for title in ("Transcript", "Recap"):
                markdown = "\n\n".join(
                    f"## {title} section {index}\n\nContent {index}"
                    for index in range(30)
                )
                screen = MarkdownPreviewScreen(title, markdown)
                app.push_screen(screen)
                await pilot.pause()

                preview_scroll = screen.query_one("#preview-scroll", VerticalScroll)
                assert preview_scroll.has_focus is True
                assert preview_scroll.max_scroll_y > 0
                assert_modal_is_centered(screen)

                await pilot.press("end")
                await pilot.pause()
                assert preview_scroll.scroll_y > 0

                screen.dismiss(None)
                await pilot.pause()

    asyncio.run(run())


def test_tui_short_modal_is_centered() -> None:
    async def run() -> None:
        app = NoteKeeperTui(FakeRuntime())
        async with app.run_test(size=(100, 40)) as pilot:
            screen = RenameScreen("Rename Player", "Alice")
            app.push_screen(screen)
            await pilot.pause()
            assert_modal_is_centered(screen)

    asyncio.run(run())


def test_tui_sync_folder_button_uses_runtime_use_case() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#sync-folder")
            for _ in range(20):
                await pilot.pause()
                if "Synced:" in str(app.query_one("#status", Static).render()):
                    break

            command = runtime.use_cases.sync_campaign_folder.commands[0]
            assert isinstance(command, SyncCampaignFolderCommand)
            assert command.campaign_id == "campaign-1"

    asyncio.run(run())


def test_tui_create_job_button_uses_selected_recording() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            recordings_table = app.query_one("#recordings-table", DataTable)
            assert recordings_table.cursor_type == "row"
            app._select_table_row(recordings_table, "audio-track-1")
            assert isinstance(app._selected_object, AudioTrack)
            assert str(app._selected_object.id) == "audio-track-1"
            campaign_list_reads = len(runtime.use_cases.list_campaigns.commands)
            app.on_button_pressed(
                SimpleNamespace(button=SimpleNamespace(id="create-job")),
            )
            await pilot.pause()

            command = (
                runtime.use_cases.create_processing_job_for_audio_track.commands[0]
            )
            assert isinstance(command, CreateProcessingJobForAudioTrackCommand)
            assert command.audio_track_id == "audio-track-1"
            assert len(runtime.use_cases.list_campaigns.commands) == campaign_list_reads
            status = str(app.query_one("#status", Static).render())
            assert "Created job job-1" in status

    asyncio.run(run())


def test_tui_run_job_button_uses_selected_job() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            jobs_table = app.query_one("#jobs-table", DataTable)
            assert jobs_table.cursor_type == "row"
            app._select_table_row(jobs_table, "job-1")
            assert isinstance(app._selected_object, ProcessingJob)
            assert str(app._selected_object.id) == "job-1"
            app.on_button_pressed(
                SimpleNamespace(button=SimpleNamespace(id="job-action")),
            )
            for _ in range(20):
                await pilot.pause()
                if runtime.use_cases.run_processing_job.commands:
                    break
            for _ in range(10):
                await pilot.pause()

            command = runtime.use_cases.run_processing_job.commands[0]
            assert isinstance(command, RunProcessingJobCommand)
            assert command.job_id == "job-1"

    asyncio.run(run())


def test_tui_restart_failed_job_button_uses_selected_failed_job() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            jobs_table = app.query_one("#jobs-table", DataTable)
            app._select_table_row(jobs_table, "job-2")
            assert isinstance(app._selected_object, ProcessingJob)
            assert str(app._selected_object.id) == "job-2"
            app.on_button_pressed(
                SimpleNamespace(button=SimpleNamespace(id="job-action")),
            )
            await pilot.pause()

            command = runtime.use_cases.restart_failed_processing_job.commands[0]
            assert isinstance(command, RestartFailedProcessingJobCommand)
            assert command.job_id == "job-2"
            assert isinstance(app._selected_object, ProcessingJob)
            assert str(app._selected_object.id) == "job-3"
            status = str(app.query_one("#status", Static).render())
            assert "Restarted job job-2 as job-3" in status

    asyncio.run(run())


def test_tui_job_action_opens_review_for_waiting_job() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        waiting_job = replace(
            runtime.use_cases.list_jobs_for_campaign.result.jobs[1],
            status=JobStatus.WAITING_FOR_REVIEW,
            transcript_id="transcript-1",
            error_message=None,
        )
        runtime.use_cases.list_jobs_for_campaign.result = ListJobsForCampaignResult(
            jobs=(
                runtime.use_cases.list_jobs_for_campaign.result.jobs[0],
                waiting_job,
            ),
        )
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            jobs_table = app.query_one("#jobs-table", DataTable)
            app._select_table_row(jobs_table, "job-2")
            app.on_button_pressed(
                SimpleNamespace(button=SimpleNamespace(id="job-action")),
            )
            await pilot.pause()

            assert isinstance(app.screen, ReviewMappingsScreen)

    asyncio.run(run())


def test_tui_review_screen_collects_player_and_custom_label_decisions() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        job = runtime.use_cases.list_jobs_for_campaign.result.jobs[0]
        waiting_job = replace(
            job,
            status=JobStatus.WAITING_FOR_REVIEW,
            transcript_id="transcript-1",
            warnings=(
                PipelineWarning(
                    kind=PipelineWarningKind.UNRESOLVED_SPEAKER_LABEL,
                    message="SPEAKER_00 is unresolved",
                    speaker_label=SpeakerLabel.anonymous("SPEAKER_00"),
                ),
                PipelineWarning(
                    kind=PipelineWarningKind.UNRESOLVED_SPEAKER_LABEL,
                    message="SPEAKER_01 is unresolved",
                    speaker_label=SpeakerLabel.anonymous("SPEAKER_01"),
                ),
            ),
        )
        participants = runtime.use_cases.list_participants.result.participants
        results = []
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            app.push_screen(
                ReviewMappingsScreen(waiting_job, participants),
                results.append,
            )
            await pilot.pause()
            screen = app.screen

            assert isinstance(screen, ReviewMappingsScreen)
            assert len(screen.query(".review-mapping")) == 2
            assert screen.query_one("#review-label-0", Input).value == "SPEAKER_00"
            assert screen.query_one("#review-label-1", Input).value == "SPEAKER_01"
            assert screen.query_one("#review-participant-0", Select).display is True
            assert screen.query_one("#review-label-0", Input).display is False

            screen.query_one("#submit", Button).press()
            await pilot.pause()
            assert app.screen is screen
            assert "Select a player for SPEAKER_00" in str(
                screen.query_one("#review-error", Static).render(),
            )

            screen.query_one("#review-participant-0", Select).value = "participant-1"
            screen.query_one("#review-mode-1", Switch).value = True
            await pilot.pause()
            assert screen.query_one("#review-participant-1", Select).display is False
            assert screen.query_one("#review-label-1", Input).display is True
            screen.query_one("#review-label-1", Input).value = "Random Guest"
            screen.query_one("#submit", Button).press()
            await pilot.pause()

            assert results == [
                (
                    ManualSpeakerMappingCommand(
                        anonymous_label="SPEAKER_00",
                        participant_id="participant-1",
                        confidence=1.0,
                    ),
                    ManualSpeakerMappingCommand(
                        anonymous_label="SPEAKER_01",
                        named_label="Random Guest",
                        confidence=1.0,
                    ),
                ),
            ]

    asyncio.run(run())


def test_tui_review_screen_defaults_to_custom_labels_without_players() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        job = runtime.use_cases.list_jobs_for_campaign.result.jobs[0]
        waiting_job = replace(
            job,
            status=JobStatus.WAITING_FOR_REVIEW,
            transcript_id="transcript-1",
            warnings=(
                PipelineWarning(
                    kind=PipelineWarningKind.UNRESOLVED_SPEAKER_LABEL,
                    message="SPEAKER_00 is unresolved",
                    speaker_label=SpeakerLabel.anonymous("SPEAKER_00"),
                ),
            ),
        )
        results = []
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            app.push_screen(ReviewMappingsScreen(waiting_job, ()), results.append)
            await pilot.pause()
            screen = app.screen

            assert isinstance(screen, ReviewMappingsScreen)
            assert screen.query_one("#review-mode-0", Switch).value is True
            assert screen.query_one("#review-label-0", Input).display is True
            screen.query_one("#submit", Button).press()
            await pilot.pause()

            assert results == [
                (
                    ManualSpeakerMappingCommand(
                        anonymous_label="SPEAKER_00",
                        named_label="SPEAKER_00",
                        confidence=1.0,
                    ),
                ),
            ]

    asyncio.run(run())


def test_tui_clear_failed_jobs_confirms_and_refreshes_current_campaign() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            clear_button = app.query_one("#clear-failed-jobs", Button)
            jobs_header = app.query_one("#jobs-header")
            assert clear_button.parent is jobs_header
            assert clear_button.disabled is False

            clear_button.press()
            await pilot.pause()
            assert isinstance(app.screen, ClearFailedJobsScreen)
            assert "Clear 1 failed job" in str(
                app.screen.query_one("Label").render(),
            )

            app.screen.query_one("#confirm-clear", Button).press()
            for _ in range(30):
                await pilot.pause()
                if runtime.use_cases.clear_failed_jobs_for_campaign.commands:
                    break
            for _ in range(30):
                await pilot.pause()
                if app.query_one("#jobs-table", DataTable).row_count == 1:
                    break

            command = runtime.use_cases.clear_failed_jobs_for_campaign.commands[0]
            assert isinstance(command, ClearFailedJobsForCampaignCommand)
            assert command.campaign_id == "campaign-1"
            assert app.query_one("#jobs-table", DataTable).row_count == 1
            assert isinstance(app._selected_object, ProcessingJob)
            assert str(app._selected_object.id) == "job-1"
            assert clear_button.disabled is True
            assert "Cleared 1 failed jobs" in str(
                app.query_one("#status", Static).render(),
            )

    asyncio.run(run())


def test_audio_file_explorer_starts_in_project_data_directory() -> None:
    explorer = AudioFileExplorerScreen()

    assert explorer.initial_location == Path("data").resolve()


def test_audio_file_explorer_accepts_absolute_file_path(tmp_path: Path) -> None:
    async def run() -> None:
        source = tmp_path / "session.wav"
        source.write_bytes(b"audio")
        selected: list[Path | None] = []
        app = NoteKeeperTui(FakeRuntime())

        async with app.run_test() as pilot:
            app.push_screen(
                AudioFileExplorerScreen(tmp_path),
                selected.append,
            )
            await pilot.pause()
            file_input = app.screen.query_one(Input)
            file_input.value = str(source.resolve())
            file_input.focus()
            await pilot.press("enter")
            await pilot.pause()

        assert selected == [source.resolve()]

    asyncio.run(run())


def test_audio_file_explorer_navigates_to_absolute_directory(tmp_path: Path) -> None:
    async def run() -> None:
        folder = tmp_path / "records"
        folder.mkdir()
        source = folder / "session.wav"
        source.write_bytes(b"audio")
        selected: list[Path | None] = []
        app = NoteKeeperTui(FakeRuntime())

        async with app.run_test() as pilot:
            app.push_screen(
                AudioFileExplorerScreen(tmp_path),
                selected.append,
            )
            await pilot.pause()
            file_input = app.screen.query_one(Input)
            file_input.value = str(folder.resolve())
            file_input.focus()
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, AudioFileExplorerScreen)
            assert file_input.value == ""
            file_input.value = source.name
            file_input.focus()
            await pilot.press("enter")
            await pilot.pause()

        assert selected == [source.resolve()]

    asyncio.run(run())


def test_voice_sample_screen_selects_and_preflights_local_file() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            screen = VoiceSampleScreen(
                runtime,
                "campaign-1",
                (("Alice", "participant-1"),),
            )
            app.push_screen(screen)
            await pilot.pause()

            assert len(screen.query("#artifact-uri")) == 0
            assert screen.query_one("#save", Button).disabled is True

            screen._select_source(Path("session.wav"))

            assert "duration: 12.00s" in str(
                screen.query_one("#metadata", Static).render(),
            )
            assert screen.query_one("#save", Button).disabled is False
            assert runtime.use_cases.inspect_local_audio_file.commands
            screen.query_one("#participant", Select).value = "participant-1"
            screen._save()

            command = runtime.use_cases.add_voice_sample.commands[-1]
            assert command.artifact_uri is None
            assert command.source_path == str(Path("session.wav").resolve())

    asyncio.run(run())


def test_recording_screen_preflight_shows_metadata() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            screen = RecordingScreen(runtime, "campaign-1")
            app.push_screen(screen)
            await pilot.pause()
            assert len(screen.query("#artifact-uri")) == 0

            screen._select_source(Path("session.wav"))

            assert "duration: 12.00s" in str(
                screen.query_one("#metadata", Static).render(),
            )
            assert screen.query_one("#submit", Button).disabled is False
            command = runtime.use_cases.inspect_local_audio_file.commands[-1]
            assert command.source_path == str(Path("session.wav").resolve())
            screen._submit()
            await pilot.pause()

            submit_command = (
                runtime.use_cases.submit_recording_for_processing.commands[-1]
            )
            assert submit_command.artifact_uri is None
            assert submit_command.source_path == str(Path("session.wav").resolve())

    asyncio.run(run())


def test_recording_screen_choose_file_opens_shared_explorer() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            screen = RecordingScreen(runtime, "campaign-1")
            app.push_screen(screen)
            await pilot.pause()

            screen.query_one("#choose-file", Button).press()
            await pilot.pause()

            assert isinstance(app.screen, AudioFileExplorerScreen)
            app.screen.dismiss(None)

    asyncio.run(run())


def test_tui_diagnostics_do_not_show_secret_values() -> None:
    async def run() -> None:
        app = NoteKeeperTui(FakeRuntime())
        async with app.run_test() as pilot:
            app._open_diagnostics()
            await pilot.pause()
            modal_text = str(app.screen.query_one(".metadata", Static).render())
            assert "deepseek configured: True" in modal_text
            assert "huggingface configured: True" in modal_text
            assert "secret" not in modal_text

    asyncio.run(run())
