"""Speaker-mapping review actions and modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static, TextArea

from notekeeper.application import (
    ApplicationError,
    ListParticipantsCommand,
    ManualSpeakerMappingCommand,
    ReviewSpeakerMappingsCommand,
)
from notekeeper.domain import DomainError, JobStatus

from .common import parse_mapping, participants_text, warnings_text


class ReviewMappingsScreen(ModalScreen[tuple[ManualSpeakerMappingCommand, ...] | None]):
    def __init__(self, job, participants) -> None:
        super().__init__()
        self.job = job
        self.participants = participants

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Review Mapping")
            yield Static(participants_text(self.participants), classes="metadata")
            yield Static(warnings_text(self.job), classes="metadata")
            yield TextArea("", id="mappings", language="text")
            yield Button("Submit", id="submit", variant="primary")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "submit":
            self.dismiss(None)
            return

        try:
            mappings = tuple(
                parse_mapping(line)
                for line in self.query_one("#mappings", TextArea).text.splitlines()
                if line.strip()
            )
        except ValueError:
            self.dismiss(None)
            return
        self.dismiss(mappings)


def open_review(app, campaign_id: str) -> None:
    job = app._selected_job()
    if job is None:
        app._set_status("Select a job")
        return
    if job.status is not JobStatus.WAITING_FOR_REVIEW:
        app._set_status("Job is not waiting for review")
        return

    participants = app.runtime.use_cases.list_participants.execute(
        ListParticipantsCommand(campaign_id=campaign_id),
    ).participants
    app.push_screen(
        ReviewMappingsScreen(job, participants),
        lambda mappings: review_selected_job(app, tuple(mappings or ())),
    )


def review_selected_job(app, mappings: tuple[ManualSpeakerMappingCommand, ...]) -> None:
    job = app._selected_job()
    if job is None or not mappings:
        return
    app.run_worker(
        lambda: app.runtime.use_cases.review_speaker_mappings.execute(
            ReviewSpeakerMappingsCommand(
                job_id=str(job.id),
                mappings=mappings,
            ),
        ),
        group="review",
        thread=True,
        exit_on_error=False,
    )
