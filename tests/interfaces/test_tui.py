import asyncio
from datetime import datetime
from types import SimpleNamespace

from textual.widgets import Button, DataTable, Input, Static

from notekeeper.application import (
    CreateProcessingJobForAudioTrackCommand,
    CreateProcessingJobForAudioTrackResult,
    GetJobStatusResult,
    InspectAudioMetadataResult,
    ListAudioTracksResult,
    ListCampaignsResult,
    ListJobsForCampaignResult,
    ListParticipantsResult,
    ListVoiceSamplesResult,
    RestartFailedProcessingJobCommand,
    RestartFailedProcessingJobResult,
    RunProcessingJobCommand,
    SyncCampaignFolderCommand,
    SyncCampaignFolderResult,
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
    ProcessingJob,
)
from notekeeper.interfaces import RuntimeDiagnostics, Stage1UseCases
from notekeeper.interfaces.tui import NoteKeeperTui, RecordingScreen, VoiceSampleScreen


class FakeUseCase:
    def __init__(self, result) -> None:
        self.result = result
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        return self.result


class FakeRestartUseCase(FakeUseCase):
    def __init__(self, result, list_jobs_use_case: FakeUseCase) -> None:
        super().__init__(result)
        self.list_jobs_use_case = list_jobs_use_case

    def execute(self, command):
        result = super().execute(command)
        existing_jobs = self.list_jobs_use_case.result.jobs
        self.list_jobs_use_case.result = ListJobsForCampaignResult(
            jobs=(*existing_jobs, result.job),
        )
        return result


class FakeJobStatusUseCase:
    def __init__(self, jobs: tuple[ProcessingJob, ...]) -> None:
        self.jobs = {str(job.id): job for job in jobs}
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        return GetJobStatusResult(job=self.jobs[str(command.job_id)])


class FakeRuntime:
    def __init__(self, *, has_campaigns: bool = True) -> None:
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
            artifact=ArtifactRef(uri="sessions/session-1.wav"),
            metadata=metadata,
            title="Session 1",
        )
        list_jobs = FakeUseCase(ListJobsForCampaignResult(jobs=jobs))
        self.use_cases = Stage1UseCases(
            create_campaign=FakeUseCase(None),
            get_campaign=FakeUseCase(None),
            list_campaigns=FakeUseCase(ListCampaignsResult(campaigns=campaigns)),
            add_participant=FakeUseCase(None),
            list_participants=FakeUseCase(
                ListParticipantsResult(participants=participants),
            ),
            add_voice_sample=FakeUseCase(None),
            list_voice_samples=FakeUseCase(ListVoiceSamplesResult(voice_samples=())),
            register_audio_track=FakeUseCase(None),
            list_audio_tracks=FakeUseCase(
                ListAudioTracksResult(
                    audio_tracks=(audio_track,) if has_campaigns else (),
                ),
            ),
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
            ),
            list_jobs_for_campaign=list_jobs,
            get_job_status=FakeJobStatusUseCase((job, second_job, restarted_job)),
            review_speaker_mappings=FakeUseCase(GetJobStatusResult(job=job)),
            generate_recap=FakeUseCase(None),
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
            assert app._selected_job_id in {"job-1", "job-2"}
            assert app._selected_audio_track_id == "audio-track-1"
            recordings_table = app.query_one("#recordings-table", DataTable)
            recording_row = recordings_table.get_row_at(0)
            assert recording_row[3] == "2"
            assert recording_row[4] == "failed"

    asyncio.run(run())


def test_tui_dashboard_loads_without_campaigns() -> None:
    async def run() -> None:
        app = NoteKeeperTui(FakeRuntime(has_campaigns=False))
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#jobs-table", DataTable).row_count == 0
            assert app.query_one("#players-table", DataTable).row_count == 0
            assert "No campaign" in str(app.query_one("#status", Static).render())

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
            app.on_data_table_row_highlighted(
                DataTable.RowHighlighted(recordings_table, 0, "audio-track-1"),
            )
            assert app._selected_audio_track_id == "audio-track-1"
            app.on_button_pressed(
                SimpleNamespace(button=SimpleNamespace(id="create-job")),
            )
            await pilot.pause()

            command = (
                runtime.use_cases.create_processing_job_for_audio_track.commands[0]
            )
            assert isinstance(command, CreateProcessingJobForAudioTrackCommand)
            assert command.audio_track_id == "audio-track-1"
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
            app.on_data_table_row_highlighted(
                DataTable.RowHighlighted(jobs_table, 1, "job-2"),
            )
            assert app._selected_job_id == "job-2"
            app.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="run-job")))
            for _ in range(20):
                await pilot.pause()
                if runtime.use_cases.run_processing_job.commands:
                    break
            for _ in range(10):
                await pilot.pause()

            command = runtime.use_cases.run_processing_job.commands[0]
            assert isinstance(command, RunProcessingJobCommand)
            assert command.job_id == "job-2"

    asyncio.run(run())


def test_tui_restart_failed_job_button_uses_selected_failed_job() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            jobs_table = app.query_one("#jobs-table", DataTable)
            app.on_data_table_row_highlighted(
                DataTable.RowHighlighted(jobs_table, 1, "job-2"),
            )
            assert app._selected_job_id == "job-2"
            app.on_button_pressed(
                SimpleNamespace(button=SimpleNamespace(id="restart-job")),
            )
            await pilot.pause()

            command = runtime.use_cases.restart_failed_processing_job.commands[0]
            assert isinstance(command, RestartFailedProcessingJobCommand)
            assert command.job_id == "job-2"
            assert app._selected_job_id == "job-3"
            status = str(app.query_one("#status", Static).render())
            assert "Restarted job job-2 as job-3" in status

    asyncio.run(run())


def test_tui_restart_failed_job_rejects_non_failed_selection() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            await pilot.pause()
            jobs_table = app.query_one("#jobs-table", DataTable)
            app.on_data_table_row_highlighted(
                DataTable.RowHighlighted(jobs_table, 0, "job-1"),
            )
            app.on_button_pressed(
                SimpleNamespace(button=SimpleNamespace(id="restart-job")),
            )
            await pilot.pause()

            assert not runtime.use_cases.restart_failed_processing_job.commands
            assert "Job is not failed" in str(app.query_one("#status", Static).render())

    asyncio.run(run())


def test_voice_sample_screen_shows_expected_artifact_uri_placeholder() -> None:
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

            assert (
                screen.query_one("#artifact-uri", Input).placeholder
                == "campaign-1/players/Alice/sample.wav"
            )

    asyncio.run(run())


def test_recording_screen_preflight_shows_metadata() -> None:
    async def run() -> None:
        runtime = FakeRuntime()
        app = NoteKeeperTui(runtime)
        async with app.run_test() as pilot:
            screen = RecordingScreen(runtime, "campaign-1")
            app.push_screen(screen)
            await pilot.pause()
            screen.query_one("#artifact-uri", Input).value = "session.wav"
            screen._run_preflight()
            assert "duration: 12.00s" in str(
                screen.query_one("#metadata", Static).render(),
            )
            assert screen.query_one("#submit", Button).disabled is False

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
