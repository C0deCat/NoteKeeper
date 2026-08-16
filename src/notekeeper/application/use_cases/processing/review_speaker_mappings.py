"""Validate speaker-review decisions and queue their application."""

from dataclasses import replace

from notekeeper.application.commands import (
    ManualSpeakerMappingCommand,
    ReviewSpeakerMappingsCommand,
)
from notekeeper.application.errors import InvalidOperationError, NotFoundError
from notekeeper.application.ports import (
    CampaignRepository,
    Clock,
    JobManager,
    JobRepository,
    SpeakerReviewSubmissionRepository,
    TranscriptRepository,
)
from notekeeper.application.results import (
    ReviewSpeakerMappingsResult,
    SpeakerReviewSubmission,
)
from notekeeper.application.use_cases.utils import (
    require_campaign,
    require_job,
    require_transcript,
)
from notekeeper.domain import (
    Campaign,
    JobStatus,
    Participant,
    ParticipantId,
    ProcessingJobId,
    SpeakerLabel,
    SpeakerMapping,
    SpeakerMappingSource,
    SpeakerMappingStatus,
)


class SubmitSpeakerMappingReview:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        transcript_repository: TranscriptRepository,
        job_repository: JobRepository,
        submission_repository: SpeakerReviewSubmissionRepository,
        job_manager: JobManager,
        clock: Clock,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._transcript_repository = transcript_repository
        self._job_repository = job_repository
        self._submission_repository = submission_repository
        self._job_manager = job_manager
        self._clock = clock

    def execute(
        self,
        command: ReviewSpeakerMappingsCommand,
    ) -> ReviewSpeakerMappingsResult:
        job = require_job(self._job_repository, ProcessingJobId(command.job_id))
        if job.status is not JobStatus.WAITING_FOR_REVIEW:
            raise InvalidOperationError("processing job must be waiting for review")
        if job.transcript_id is None:
            raise InvalidOperationError("processing job has no transcript to review")

        campaign = require_campaign(self._campaign_repository, job.campaign_id)
        transcript = require_transcript(
            self._transcript_repository,
            job.transcript_id,
        )
        mappings = _build_manual_mappings(campaign, command.mappings)
        submission = SpeakerReviewSubmission(
            job_id=job.id,
            transcript_id=transcript.id,
            mappings=mappings,
        )
        self._submission_repository.save(submission)
        queued_job = replace(
            job,
            status=JobStatus.QUEUED,
            updated_at=self._clock.now(),
            error_message=None,
        )
        if not self._job_repository.save_if_status(
            queued_job,
            JobStatus.WAITING_FOR_REVIEW,
        ):
            self._submission_repository.delete(job.id)
            raise InvalidOperationError(
                "processing job is no longer waiting for review"
            )
        try:
            self._job_manager.enqueue(job.id)
        except Exception:
            self._job_repository.save_if_status(job, JobStatus.QUEUED)
            self._submission_repository.delete(job.id)
            raise
        return ReviewSpeakerMappingsResult(
            job=queued_job,
            transcript=transcript,
            recap=None,
            warnings=job.warnings,
            applied_mappings=(),
        )


ReviewSpeakerMappings = SubmitSpeakerMappingReview


def _build_manual_mappings(
    campaign: Campaign,
    commands: tuple[ManualSpeakerMappingCommand, ...],
) -> tuple[SpeakerMapping, ...]:
    participants = {
        participant.id: participant for participant in campaign.participants
    }
    mappings: list[SpeakerMapping] = []
    reviewed_labels: set[SpeakerLabel] = set()
    for command in commands:
        anonymous_label = SpeakerLabel.anonymous(command.anonymous_label)
        if anonymous_label in reviewed_labels:
            raise InvalidOperationError(
                f"speaker label {anonymous_label.value} has multiple review decisions"
            )
        reviewed_labels.add(anonymous_label)
        participant_id = _optional_text(command.participant_id)
        named_label = _optional_text(command.named_label)
        if (participant_id is None) == (named_label is None):
            raise InvalidOperationError(
                "manual speaker mapping must include exactly one of "
                "participant_id or named_label"
            )
        participant = None
        if participant_id is not None:
            participant_key = ParticipantId(participant_id)
            participant = participants.get(participant_key)
            if participant is None:
                raise NotFoundError(f"participant {participant_key} was not found")
        mappings.append(
            _manual_mapping(
                command,
                anonymous_label=anonymous_label,
                participant=participant,
                named_label=named_label,
            )
        )
    return tuple(mappings)


def _manual_mapping(
    command: ManualSpeakerMappingCommand,
    *,
    anonymous_label: SpeakerLabel,
    participant: Participant | None,
    named_label: str | None,
) -> SpeakerMapping:
    resolved_label = (
        participant.display_name if participant is not None else named_label
    )
    if resolved_label is None:
        raise InvalidOperationError("manual speaker mapping has no resolved label")
    return SpeakerMapping(
        anonymous_label=anonymous_label,
        named_label=SpeakerLabel.named(resolved_label),
        participant_id=participant.id if participant is not None else None,
        confidence=command.confidence,
        source=SpeakerMappingSource.MANUAL,
        status=SpeakerMappingStatus.CONFIRMED,
    )


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


__all__ = ["ReviewSpeakerMappings", "SubmitSpeakerMappingReview"]
