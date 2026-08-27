"""Textual dashboard application composition."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import cast

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ItemGrid, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    ProgressBar,
    RichLog,
    Select,
    Static,
)
from textual.worker import Worker, WorkerState

from notekeeper.application import (
    ApplicationError,
    CancelProcessingJobResult,
    ClearFailedJobsForCampaignCommand,
    ClearFailedJobsForCampaignResult,
    ConsoleLogEvent,
    DeleteProcessingJobResult,
    GenerateRecapResult,
    GetCampaignCommand,
    ProgressEvent,
    QueueProcessingJobResult,
    SyncCampaignFolderResult,
)
from notekeeper.domain import (
    AudioTrack,
    DomainError,
    JobStatus,
    Participant,
    ProcessingJob,
)

from ..contracts import InterfaceRuntime
from . import (
    campaign_app,
    dashboard_progress,
    dashboard_refresh,
    dashboard_selection,
    diagnostics_app,
    job_app,
    participant_app,
    recap_app,
    recording_app,
    review_app,
    sample_app,
    transcript_app,
)
from .campaign_management_screen import ManageCampaignsScreen
from .campaign_settings_screen import CampaignSettingsScreen
from .clear_failed_jobs_screen import ClearFailedJobsScreen
from .common import sync_result_status
from .dashboard_messages import (
    ConsoleLogChanged,
    DashboardWarning,
    SelectedObject,
)
from .ellipsis_select import EllipsisSelect
from .identifier_data_table import IdentifierDataTable
from .login_screen import LoginScreen
from .participant_app import AddParticipantScreen
from .responsive_topbar import ResponsiveTopbar
from .settings_screen import SettingsScreen
from .tui_log_handler import TuiLogHandler


class NoteKeeperTui(App[None]):
    """Dashboard-first Textual interface for NoteKeeper."""

    CSS_PATH = Path(__file__).with_name("styles.tcss")

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("d", "diagnostics", "Diagnostics"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, runtime: InterfaceRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        self._selected_campaign_id: str | None = None
        self._selected_object: SelectedObject | None = None
        self._dashboard_jobs: dict[str, ProcessingJob] = {}
        self._dashboard_audio_tracks: dict[str, AudioTrack] = {}
        self._dashboard_participants: dict[str, Participant] = {}
        self._dashboard_warnings: dict[str, DashboardWarning] = {}
        self._participant_ids_with_samples: set[str] = set()
        self._campaign_has_participants = False
        self._campaign_is_processing_ready = False
        self._failed_job_count = 0
        self._campaign_has_active_jobs = False
        self._clear_failed_jobs_in_progress = False
        self._job_delete_in_progress = False
        self._job_cancel_in_progress = False
        self._recap_generation_in_progress = False
        self._active_progress_events: dict[str, ProgressEvent] = {}
        self._progress_unsubscribes: dict[str, Callable[[], None]] = {}
        self._dashboard_unsubscribe: Callable[[], None] | None = None
        self._console_unsubscribe: Callable[[], None] | None = None
        self._tui_log_handler: TuiLogHandler | None = None
        self._notekeeper_logger_propagate = True
        self._dashboard_refresh_scheduled = False
        self._pending_full_refresh = False
        self._pending_content_refresh = False
        self._pending_selected_job_id: str | None = None
        self._review_job_id: str | None = None
        self._dashboard_initialized = False

    def compose(self) -> ComposeResult:
        auth = getattr(self.runtime, "auth", None)
        auth_enabled = auth is not None and auth.enabled
        yield Header()
        with ResponsiveTopbar(id="topbar"):
            with Horizontal(id="topbar-left"):
                with Horizontal(id="topbar-selectors"):
                    yield EllipsisSelect(
                        (),
                        prompt="Workspace",
                        id="workspace-select",
                    )
                    yield EllipsisSelect(
                        (),
                        prompt="Campaign",
                        id="campaign-select",
                    )
                with Horizontal(id="topbar-actions"):
                    yield Button("Campaigns", id="manage-campaign")
                    yield Button(
                        "⚙",
                        id="settings",
                        classes="icon-button",
                        tooltip="Settings",
                        compact=True,
                    )
            with Horizontal(id="account-status"):
                if auth_enabled:
                    yield Button(
                        "⇥",
                        id="logout",
                        classes="icon-button",
                        variant="error",
                        tooltip="Logout",
                        compact=True,
                    )
                with Vertical(id="account-copy"):
                    yield Static("0 jobs", id="job-count")
                    if auth_enabled:
                        yield Static("", id="auth-user")
        with ItemGrid(
            id="campaign-actions",
            min_column_width=20,
            stretch_height=False,
        ):
            yield Button("Refresh", id="refresh", variant="primary")
            yield Button("Sync Folder", id="sync-folder")
            yield Button("Add Player", id="add-player")
            yield Button("Add Voice Sample", id="add-sample")
            yield Button("Submit Recording", id="submit-recording")
            yield Button("Diagnostics", id="diagnostics")
        with Horizontal(id="dashboard"):
            with VerticalScroll(id="actions"):
                yield Button("Create Job", id="create-job")
                yield Button("Rename Recording", id="rename-recording")
                yield Button("Remove Recording", id="remove-recording", variant="error")
                yield Button("Rename Player", id="rename-player")
                yield Button("Remove Player", id="remove-player", variant="error")
                yield Button(
                    "Remove Voice Sample",
                    id="remove-voice-sample",
                    variant="error",
                )
                yield Button("Run", id="job-action", variant="success")
                yield Button("Delete", id="delete-job", variant="error")
                yield Button("Cancel", id="cancel-job", variant="warning")
                yield Button("Recreate Recap", id="recreate-recap")
                yield Button("Preview Transcript", id="preview-transcript")
                yield Button("Preview Recap", id="preview-recap")
                yield Button("Export Transcript", id="export-transcript")
                yield Button("Export Recap", id="export-recap")
                with Vertical(id="progress-panel"):
                    yield Static("", id="progress-stage")
                    yield ProgressBar(total=100, id="job-progress")
                    yield Static("", id="progress-time")
            with Vertical(id="content"):
                with Horizontal(id="jobs-header"):
                    yield Label("Jobs")
                    yield Button(
                        "Clear Failed Jobs",
                        id="clear-failed-jobs",
                        variant="error",
                    )
                yield IdentifierDataTable(
                    id="jobs-table",
                    classes="panel short-panel",
                    show_cursor=False,
                )
                yield Label("Recordings")
                yield IdentifierDataTable(
                    id="recordings-table",
                    classes="panel short-panel",
                    show_cursor=False,
                )
                yield Label("Players")
                yield IdentifierDataTable(
                    id="players-table",
                    classes="panel short-panel",
                    show_cursor=False,
                )
                yield Label("Warnings and errors")
                yield IdentifierDataTable(
                    id="warnings-table",
                    classes="panel short-panel",
                    show_cursor=False,
                )
        with Vertical(id="console-panel", classes="collapsed"):
            yield Button("Logs ▲", id="console-toggle")
            yield RichLog(
                id="console-log",
                max_lines=1000,
                min_width=1,
                wrap=True,
                markup=False,
                auto_scroll=True,
            )
        yield Footer()

    def on_mount(self) -> None:
        self._setup_console_logging()
        auth = getattr(self.runtime, "auth", None)
        if auth is not None and auth.enabled and auth.current_user is None:
            self.push_screen(LoginScreen(self.runtime), self._authenticated)
            return
        self._initialize_dashboard()

    def _initialize_dashboard(self) -> None:
        auth = getattr(self.runtime, "auth", None)
        auth_enabled = auth is not None and auth.enabled
        if auth is not None and auth_enabled and auth.current_user is not None:
            user_label = self.query_one("#auth-user", Static)
            user_label.update(auth.current_user.login)
            user_label.tooltip = auth.current_user.login
        self._refresh_workspace_select()
        self.runtime.start_job_manager(recover_queued=True)
        if not self._dashboard_initialized:
            self._dashboard_unsubscribe = self.runtime.dashboard_events.subscribe(
                self._on_dashboard_changed,
            )
            self.query_one("#progress-panel", Vertical).display = False
            self._setup_tables()
            self._dashboard_initialized = True
        self.refresh_dashboard()

    def _authenticated(self, _user: object) -> None:
        self._selected_campaign_id = None
        self._selected_object = None
        self._initialize_dashboard()

    def action_refresh(self) -> None:
        self.refresh_dashboard()

    def action_diagnostics(self) -> None:
        self._open_diagnostics()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "workspace-select":
            if event.value in (Select.BLANK, Select.NULL):
                return
            try:
                current = self._current_workspace_id()
                selected = str(event.value)
                if current != selected:
                    self.runtime.switch_workspace(selected)
                    self._selected_campaign_id = None
                    self._selected_object = None
                    self._refresh_workspace_select()
                    self.refresh_dashboard()
            except (ApplicationError, DomainError, ValueError) as exc:
                self._write_ui_log(str(exc))
            return
        if event.select.id != "campaign-select":
            return
        previous_campaign_id = self._selected_campaign_id
        if event.value in (Select.BLANK, Select.NULL):
            self._selected_campaign_id = None
        else:
            self._selected_campaign_id = str(event.value)
        if self._selected_campaign_id != previous_campaign_id:
            self._selected_object = None
        self.refresh_dashboard(update_campaigns=False)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not self._event_matches_table_cursor(event.data_table, event.row_key):
            return
        self._select_table_row(event.data_table, event.row_key, announce=True)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if not self._event_matches_table_cursor(event.data_table, event.row_key):
            return
        self._select_table_row(event.data_table, event.row_key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "refresh":
            self.refresh_dashboard()
        elif button_id == "manage-campaign":
            self._open_manage_campaigns()
        elif button_id == "settings":
            self._open_settings()
        elif button_id == "logout":
            self.runtime.auth.logout()
            self._selected_campaign_id = None
            self._selected_object = None
            self.push_screen(LoginScreen(self.runtime), self._authenticated)
        elif button_id == "sync-folder":
            self._with_campaign(self._sync_campaign_folder)
        elif button_id == "add-player":
            self._with_campaign(
                lambda campaign_id: self.push_screen(
                    AddParticipantScreen(),
                    lambda name: self._add_participant(campaign_id, name),
                ),
            )
        elif button_id == "add-sample":
            self._with_campaign(self._open_add_sample)
        elif button_id == "submit-recording":
            self._with_campaign(self._open_submit_recording)
        elif button_id == "create-job":
            self._create_job_for_selected_audio_track()
        elif button_id == "rename-recording":
            if isinstance(self._selected_object, AudioTrack):
                recording_app.open_rename_recording(self, self._selected_object)
        elif button_id == "remove-recording":
            if isinstance(self._selected_object, AudioTrack):
                recording_app.confirm_remove_recording(self, self._selected_object)
        elif button_id == "rename-player":
            if isinstance(self._selected_object, Participant):
                participant_app.open_rename_participant(self, self._selected_object)
        elif button_id == "remove-player":
            if isinstance(self._selected_object, Participant):
                participant_app.confirm_remove_participant(self, self._selected_object)
        elif button_id == "remove-voice-sample":
            if isinstance(self._selected_object, Participant):
                sample_app.open_remove_sample(self, self._selected_object)
        elif button_id == "job-action":
            self._perform_selected_job_action()
        elif button_id == "delete-job":
            job_app.confirm_delete_selected_job(self)
        elif button_id == "cancel-job":
            job_app.confirm_cancel_selected_job(self)
        elif button_id == "clear-failed-jobs":
            self._confirm_clear_failed_jobs()
        elif button_id == "recreate-recap":
            self._recreate_recap()
        elif button_id == "preview-transcript":
            self._preview_transcript()
        elif button_id == "preview-recap":
            self._preview_recap()
        elif button_id == "export-transcript":
            self._export_transcript()
        elif button_id == "export-recap":
            self._export_recap()
        elif button_id == "diagnostics":
            self._open_diagnostics()
        elif button_id == "console-toggle":
            self._set_console_expanded(self.query_one("#console-panel").has_class("collapsed"))

    def _setup_console_logging(self) -> None:
        if self._console_unsubscribe is None:
            self._console_unsubscribe = self.runtime.console_logs.subscribe(
                self._on_console_log_event,
            )
        if self._tui_log_handler is not None:
            return
        logger = logging.getLogger("notekeeper")
        self._notekeeper_logger_propagate = logger.propagate
        logger.propagate = False
        self._tui_log_handler = TuiLogHandler(self._on_console_log_event)
        logger.addHandler(self._tui_log_handler)

    def _teardown_console_logging(self) -> None:
        if self._console_unsubscribe is not None:
            self._console_unsubscribe()
            self._console_unsubscribe = None
        if self._tui_log_handler is not None:
            logger = logging.getLogger("notekeeper")
            logger.removeHandler(self._tui_log_handler)
            logger.propagate = self._notekeeper_logger_propagate
            self._tui_log_handler = None

    def _on_console_log_event(self, event: ConsoleLogEvent) -> None:
        self.post_message(ConsoleLogChanged(event))

    def on_console_log_changed(self, message: ConsoleLogChanged) -> None:
        event = message.event
        operation = event.operation_id[-8:] if event.operation_id else "app"
        prefix = Text(f"[{operation}] [{event.source.value}] ", style="dim")
        prefix.append_text(Text.from_ansi(event.text))
        self.query_one("#console-log", RichLog).write(prefix)

    def _set_console_expanded(self, expanded: bool) -> None:
        panel = self.query_one("#console-panel")
        panel.set_class(not expanded, "collapsed")
        self.query_one("#console-toggle", Button).label = (
            "Logs ▼" if expanded else "Logs ▲"
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.group not in {
            "cleanup",
            "job",
            "job-delete",
            "job-cancel",
            "recap",
            "review",
            "sync",
        }:
            return

        if event.state is WorkerState.RUNNING:
            if event.worker.group == "sync":
                self._write_ui_log("Syncing")
            elif event.worker.group == "cleanup":
                self._write_ui_log("Clearing failed jobs")
            elif event.worker.group == "job-delete":
                self._write_ui_log("Deleting job")
            elif event.worker.group == "job-cancel":
                self._write_ui_log("Canceling job")
            elif event.worker.group == "recap":
                self._write_ui_log("Recreating recap")
            else:
                self._write_ui_log("Running")
        elif event.state is WorkerState.SUCCESS:
            if event.worker.group == "review":
                self._review_job_id = None
                self._update_action_buttons()
            if event.worker.group in {"job", "recap", "review"}:
                self._hide_progress_if_inactive()
            if event.worker.group == "sync":
                result = cast(SyncCampaignFolderResult, event.worker.result)
                message = sync_result_status(result)
                self._write_ui_log(message)
                self.notify(message)
            elif event.worker.group == "cleanup":
                self._clear_failed_jobs_in_progress = False
                result = cast(
                    ClearFailedJobsForCampaignResult,
                    event.worker.result,
                )
                deleted_count = len(result.deleted_job_ids)
                message = f"Cleared {deleted_count} failed jobs"
                self._write_ui_log(message)
                self.notify(message)
            elif event.worker.group == "job-delete":
                self._job_delete_in_progress = False
                result = cast(DeleteProcessingJobResult, event.worker.result)
                message = f"Deleted job {result.job_id}"
                self._write_ui_log(message)
                self.notify(message)
            elif event.worker.group == "job-cancel":
                self._job_cancel_in_progress = False
                result = cast(CancelProcessingJobResult, event.worker.result)
                message = f"Canceled job {result.job.id}"
                self._write_ui_log(message)
                self.notify(message)
            elif event.worker.group == "recap":
                self._recap_generation_in_progress = False
                result = cast(GenerateRecapResult, event.worker.result)
                message = f"Recreated recap {result.recap.id}"
                self._write_ui_log(message)
                self.notify(message)
            elif event.worker.group == "job":
                result = cast(QueueProcessingJobResult, event.worker.result)
                message = f"Queued job {result.job.id}"
                self._write_ui_log(message)
                self.notify(message)
            elif event.worker.group == "review":
                self._write_ui_log("Queued reviewed job")
            else:
                self._write_ui_log("Done")
        elif event.state is WorkerState.ERROR:
            if event.worker.group == "review":
                self._review_job_id = None
                self._update_action_buttons()
            if event.worker.group in {"job", "recap", "review"}:
                self._hide_progress_if_inactive()
            if event.worker.group == "cleanup":
                self._clear_failed_jobs_in_progress = False
                self._update_action_buttons()
            elif event.worker.group == "job-delete":
                self._job_delete_in_progress = False
                self._update_action_buttons()
            elif event.worker.group == "job-cancel":
                self._job_cancel_in_progress = False
                self._update_action_buttons()
            elif event.worker.group == "recap":
                self._recap_generation_in_progress = False
                self._update_action_buttons()
            message = str(event.worker.error) if event.worker.error else "worker failed"
            self._write_ui_log(message)
            self.notify(message, severity="error")
        elif event.state is WorkerState.CANCELLED:
            if event.worker.group == "review":
                self._review_job_id = None
                self._update_action_buttons()
            if event.worker.group in {"job", "recap", "review"}:
                self._hide_progress_if_inactive()
            if event.worker.group == "cleanup":
                self._clear_failed_jobs_in_progress = False
                self._update_action_buttons()
            elif event.worker.group == "job-delete":
                self._job_delete_in_progress = False
                self._update_action_buttons()
            elif event.worker.group == "job-cancel":
                self._job_cancel_in_progress = False
                self._update_action_buttons()
            elif event.worker.group == "recap":
                self._recap_generation_in_progress = False
                self._update_action_buttons()

    refresh_dashboard = dashboard_refresh.refresh_dashboard

    _setup_tables = dashboard_refresh._setup_tables

    _refresh_campaign_select = dashboard_refresh._refresh_campaign_select

    _refresh_campaign_panels = dashboard_refresh._refresh_campaign_panels

    _on_dashboard_changed = dashboard_refresh._on_dashboard_changed

    on_dashboard_invalidated = dashboard_refresh.on_dashboard_invalidated

    on_screen_resume = dashboard_refresh.on_screen_resume

    _schedule_dashboard_refresh = dashboard_refresh._schedule_dashboard_refresh

    _flush_dashboard_refresh = dashboard_refresh._flush_dashboard_refresh

    _clear_tables = dashboard_refresh._clear_tables

    _reset_table = dashboard_refresh._reset_table

    _select_table_row = dashboard_refresh._select_table_row

    _event_matches_table_cursor = dashboard_refresh._event_matches_table_cursor

    _select_job_after_refresh = dashboard_refresh._select_job_after_refresh

    _update_action_buttons = dashboard_selection._update_action_buttons

    _set_button_disabled = dashboard_selection._set_button_disabled

    _set_button_display = dashboard_selection._set_button_display

    _selected_object_key = dashboard_selection._selected_object_key

    _restore_selected_object = dashboard_selection._restore_selected_object

    _sync_table_selection = dashboard_selection._sync_table_selection

    def _open_manage_campaigns(self) -> None:
        self.push_screen(
            ManageCampaignsScreen(self.runtime, self._selected_campaign_id),
            self._finish_manage_campaigns,
        )

    def _open_settings(self) -> None:
        if self._has_settings_service():
            campaign_id = self._selected_campaign_id
            campaign_name = None
            if campaign_id is not None:
                try:
                    campaign_name = self.runtime.use_cases.campaigns.get.execute(
                        GetCampaignCommand(campaign_id=campaign_id),
                    ).campaign.name
                except (ApplicationError, DomainError, ValueError) as exc:
                    self._write_ui_log(str(exc))
                    return
            self.push_screen(
                SettingsScreen(
                    self.runtime,
                    campaign_id,
                    campaign_name,
                )
            )
            return
        campaign_id = self._selected_campaign_id
        if campaign_id is None:
            self._write_ui_log("Select a campaign")
            return
        try:
            campaign = self.runtime.use_cases.campaigns.get.execute(
                GetCampaignCommand(campaign_id=campaign_id),
            ).campaign
        except (ApplicationError, DomainError, ValueError) as exc:
            self._write_ui_log(str(exc))
            return
        self.push_screen(
            CampaignSettingsScreen(
                self.runtime,
                campaign_id,
                campaign.name,
            ),
        )

    def _has_settings_service(self) -> bool:
        try:
            return self.runtime.use_cases.settings is not None
        except (AttributeError, ApplicationError):
            return False

    def _current_workspace_id(self) -> str | None:
        if not self._has_settings_service():
            return None
        service = self.runtime.use_cases.settings
        return str(service.get_workspace().workspace_id) if service is not None else None

    def _refresh_workspace_select(self) -> None:
        selector = self.query_one("#workspace-select", Select)
        if not self._has_settings_service():
            selector.display = False
            return
        try:
            workspaces = self.runtime.list_workspaces()
            selector.set_options(
                (workspace.name, str(workspace.id)) for workspace in workspaces
            )
            current = self._current_workspace_id()
            if current is not None:
                selector.value = current
            selector.display = True
        except (AttributeError, ApplicationError, DomainError, ValueError):
            selector.display = False

    def _finish_manage_campaigns(self, campaign_id: str | None) -> None:
        if campaign_id != self._selected_campaign_id:
            self._selected_object = None
        self._selected_campaign_id = campaign_id
        self.refresh_dashboard()

    def _add_participant(self, campaign_id: str, display_name: str | None) -> None:
        participant_app.add_participant(self, campaign_id, display_name)

    def _open_add_sample(self, campaign_id: str) -> None:
        sample_app.open_add_sample(self, campaign_id)

    def _open_submit_recording(self, campaign_id: str) -> None:
        recording_app.open_submit_recording(self, campaign_id)

    def _open_review(self, campaign_id: str) -> None:
        review_app.open_review(self, campaign_id)

    def _perform_selected_job_action(self) -> None:
        job = self._selected_job()
        if job is None:
            self._write_ui_log("Select a job")
        elif job.status is JobStatus.PENDING:
            self._run_selected_job()
        elif job.status in {JobStatus.FAILED, JobStatus.CANCELED}:
            self._restart_selected_failed_job()
        elif job.status is JobStatus.WAITING_FOR_REVIEW:
            self._with_campaign(self._open_review)
        else:
            self._write_ui_log("No action is available for this job")

    def _confirm_clear_failed_jobs(self) -> None:
        if self._selected_campaign_id is None:
            self._write_ui_log("Select a campaign")
            return
        if self._failed_job_count == 0:
            self._write_ui_log("No failed jobs to clear")
            return
        if self._clear_failed_jobs_in_progress:
            return
        self.push_screen(
            ClearFailedJobsScreen(self._failed_job_count),
            self._clear_failed_jobs,
        )

    def _clear_failed_jobs(self, confirmed: bool | None) -> None:
        campaign_id = self._selected_campaign_id
        if not confirmed or campaign_id is None:
            return
        self._clear_failed_jobs_in_progress = True
        self._update_action_buttons()
        self.run_worker(
            lambda: self.runtime.use_cases.jobs.clear_failed.execute(
                ClearFailedJobsForCampaignCommand(campaign_id=campaign_id),
            ),
            group="cleanup",
            thread=True,
            exit_on_error=False,
        )

    def _run_selected_job(self) -> None:
        job_app.run_selected_job(self)

    def _create_job_for_selected_audio_track(self) -> None:
        job_app.create_job_for_selected_audio_track(self)

    def _restart_selected_failed_job(self) -> None:
        job_app.restart_selected_failed_job(self)

    def _sync_campaign_folder(self, campaign_id: str) -> None:
        campaign_app.sync_campaign_folder(self, campaign_id)

    def _preview_transcript(self) -> None:
        transcript_app.preview_transcript(self)

    def _recreate_recap(self) -> None:
        recap_app.recreate_recap(self)

    def _preview_recap(self) -> None:
        recap_app.preview_recap(self)

    def _export_transcript(self) -> None:
        transcript_app.export_transcript(self)

    def _export_recap(self) -> None:
        recap_app.export_recap(self)

    def _open_diagnostics(self) -> None:
        diagnostics_app.open_diagnostics(self)

    _selected_job = dashboard_progress._selected_job

    _with_campaign = dashboard_progress._with_campaign

    _write_ui_log = dashboard_progress._write_ui_log

    _set_job_count = dashboard_progress._set_job_count

    _progress = dashboard_progress._progress

    _watch_progress = dashboard_progress._watch_progress

    _on_progress_event = dashboard_progress._on_progress_event

    on_progress_changed = dashboard_progress.on_progress_changed

    _apply_progress_event = dashboard_progress._apply_progress_event

    _show_selected_progress = dashboard_progress._show_selected_progress

    _sync_progress_subscriptions = dashboard_progress._sync_progress_subscriptions

    _selected_job_id = dashboard_progress._selected_job_id

    _hide_progress = dashboard_progress._hide_progress

    _hide_progress_if_inactive = dashboard_progress._hide_progress_if_inactive

    def on_unmount(self) -> None:
        dashboard_progress.on_unmount(self)
        self._teardown_console_logging()


def run_tui(runtime: InterfaceRuntime) -> None:
    NoteKeeperTui(runtime).run()
