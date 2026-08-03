"""Speaker-mapping review actions and modal screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch

from notekeeper.application import (
    ListParticipantsCommand,
    ManualSpeakerMappingCommand,
    ReviewSpeakerMappingsCommand,
)
from notekeeper.domain import (
    JobStatus,
    Participant,
    PipelineWarningKind,
    ProcessingJob,
)

from .common import warnings_text

if TYPE_CHECKING:
    from .tui import NoteKeeperTui


class ReviewMappingsScreen(ModalScreen[tuple[ManualSpeakerMappingCommand, ...] | None]):
    def __init__(
        self,
        job: ProcessingJob,
        participants: tuple[Participant, ...],
    ) -> None:
        super().__init__()
        self.job = job
        self.participants = participants
        self.unresolved_labels = tuple(
            sorted(
                {
                    warning.speaker_label.value
                    for warning in job.warnings
                    if warning.kind is PipelineWarningKind.UNRESOLVED_SPEAKER_LABEL
                    and warning.speaker_label is not None
                },
            ),
        )

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Review Mapping")
            yield Static(warnings_text(self.job), classes="metadata")
            with Vertical(classes="review-mappings"):
                for index, anonymous_label in enumerate(self.unresolved_labels):
                    use_custom_label = not self.participants
                    with Vertical(classes="review-mapping"):
                        yield Label(anonymous_label, classes="review-speaker-label")
                        with Horizontal(classes="review-mode"):
                            yield Label("Select Existing Player")
                            yield Switch(
                                value=use_custom_label,
                                id=f"review-mode-{index}",
                            )
                            yield Label("Type Any Label")
                        participant_select = Select(
                            tuple(
                                (
                                    f"{participant.display_name} ({participant.id})",
                                    str(participant.id),
                                )
                                for participant in self.participants
                            ),
                            prompt="Player",
                            id=f"review-participant-{index}",
                        )
                        participant_select.display = not use_custom_label
                        yield participant_select
                        label_input = Input(
                            value=anonymous_label,
                            id=f"review-label-{index}",
                        )
                        label_input.display = use_custom_label
                        yield label_input
            if not self.unresolved_labels:
                yield Static("No unresolved speaker labels", classes="review-error")
            yield Static("", id="review-error", classes="review-error")
            yield Button(
                "Submit",
                id="submit",
                variant="primary",
                disabled=not self.unresolved_labels,
            )
            yield Button("Cancel", id="cancel")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        switch_id = event.switch.id
        if switch_id is None or not switch_id.startswith("review-mode-"):
            return
        index = switch_id.removeprefix("review-mode-")
        self.query_one(f"#review-participant-{index}", Select).display = not event.value
        self.query_one(f"#review-label-{index}", Input).display = event.value
        self.query_one("#review-error", Static).update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "submit":
            self.dismiss(None)
            return

        mappings: list[ManualSpeakerMappingCommand] = []
        for index, anonymous_label in enumerate(self.unresolved_labels):
            if self.query_one(f"#review-mode-{index}", Switch).value:
                named_label = self.query_one(
                    f"#review-label-{index}",
                    Input,
                ).value.strip()
                if not named_label:
                    self._show_error(f"Enter a label for {anonymous_label}")
                    return
                mappings.append(
                    ManualSpeakerMappingCommand(
                        anonymous_label=anonymous_label,
                        named_label=named_label,
                        confidence=1.0,
                    ),
                )
                continue

            participant_id = self.query_one(
                f"#review-participant-{index}",
                Select,
            ).value
            if participant_id in (Select.BLANK, Select.NULL):
                self._show_error(f"Select a player for {anonymous_label}")
                return
            mappings.append(
                ManualSpeakerMappingCommand(
                    anonymous_label=anonymous_label,
                    participant_id=str(participant_id),
                    confidence=1.0,
                ),
            )

        self.dismiss(tuple(mappings))

    def _show_error(self, message: str) -> None:
        self.query_one("#review-error", Static).update(message)


def open_review(app: NoteKeeperTui, campaign_id: str) -> None:
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


def review_selected_job(
    app: NoteKeeperTui,
    mappings: tuple[ManualSpeakerMappingCommand, ...],
) -> None:
    job = app._selected_job()
    if job is None or not mappings:
        return
    app._review_job_id = str(job.id)
    app._update_action_buttons()
    app._watch_progress(str(job.id))
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
