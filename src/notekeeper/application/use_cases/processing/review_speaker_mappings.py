"""Review speaker mappings use case."""

from dataclasses import replace

from notekeeper.application.commands import (
    ManualSpeakerMappingCommand,
    ReviewSpeakerMappingsCommand,
)
from notekeeper.application.errors import InvalidOperationError, NotFoundError
from notekeeper.application.ports import (
    CampaignRepository,
    Clock,
    IdGenerator,
    JobRepository,
    RecapGenerator,
    RecapRepository,
    SpeakerMappingRepository,
    Tokenizer,
    TranscriptRepository,
)
from notekeeper.application.results import (
    ReviewSpeakerMappingsResult,
    SpeakerMappingRecord,
)
from notekeeper.application.use_cases._recaps import generate_recap_for_transcript
from notekeeper.application.use_cases.utils import (
    _require_campaign,
    _require_job,
    _require_transcript,
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
    TranscriptId,
    apply_speaker_mappings,
)


class ReviewSpeakerMappings:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        transcript_repository: TranscriptRepository,
        recap_repository: RecapRepository,
        job_repository: JobRepository,
        speaker_mapping_repository: SpeakerMappingRepository,
        tokenizer: Tokenizer,
        recap_generator: RecapGenerator,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._transcript_repository = transcript_repository
        self._recap_repository = recap_repository
        self._job_repository = job_repository
        self._speaker_mapping_repository = speaker_mapping_repository
        self._tokenizer = tokenizer
        self._recap_generator = recap_generator
        self._clock = clock
        self._id_generator = id_generator

    def execute(
        self,
        command: ReviewSpeakerMappingsCommand,
    ) -> ReviewSpeakerMappingsResult:
        job = _require_job(self._job_repository, ProcessingJobId(command.job_id))
        if job.status is not JobStatus.WAITING_FOR_REVIEW:
            raise InvalidOperationError("processing job must be waiting for review")
        if job.transcript_id is None:
            raise InvalidOperationError("processing job has no transcript to review")

        campaign = _require_campaign(self._campaign_repository, job.campaign_id)
        transcript = _require_transcript(
            self._transcript_repository,
            job.transcript_id,
        )
        mappings = _build_manual_mappings(campaign, command.mappings)
        mapped = apply_speaker_mappings(campaign, transcript, mappings)
        self._transcript_repository.save(mapped.transcript)
        self._speaker_mapping_repository.save_many(
            _mapping_records(
                job_id=job.id,
                transcript_id=mapped.transcript.id,
                mappings=mappings,
                warning_count=len(mapped.warnings),
            ),
        )

        if mapped.warnings:
            waiting_job = replace(
                job,
                updated_at=self._clock.now(),
                warnings=mapped.warnings,
            )
            self._job_repository.save(waiting_job)
            return ReviewSpeakerMappingsResult(
                job=waiting_job,
                transcript=mapped.transcript,
                recap=None,
                warnings=mapped.warnings,
                applied_mappings=mapped.applied_mappings,
            )

        recap = generate_recap_for_transcript(
            mapped.transcript,
            id_generator=self._id_generator,
            tokenizer=self._tokenizer,
            recap_generator=self._recap_generator,
            recap_repository=self._recap_repository,
        )
        completed_job = replace(
            job,
            status=JobStatus.COMPLETED,
            updated_at=self._clock.now(),
            transcript_id=mapped.transcript.id,
            recap_id=recap.id,
            warnings=(),
        )
        self._job_repository.save(completed_job)
        return ReviewSpeakerMappingsResult(
            job=completed_job,
            transcript=mapped.transcript,
            recap=recap,
            warnings=(),
            applied_mappings=mapped.applied_mappings,
        )


def _build_manual_mappings(
    campaign: Campaign,
    commands: tuple[ManualSpeakerMappingCommand, ...],
) -> tuple[SpeakerMapping, ...]:
    participants = {participant.id: participant for participant in campaign.participants}
    mappings: list[SpeakerMapping] = []
    for command in commands:
        participant_id = ParticipantId(command.participant_id)
        participant = participants.get(participant_id)
        if participant is None:
            raise NotFoundError(f"participant {participant_id} was not found")

        mappings.append(_manual_mapping(command, participant))

    return tuple(mappings)


def _manual_mapping(
    command: ManualSpeakerMappingCommand,
    participant: Participant,
) -> SpeakerMapping:
    return SpeakerMapping(
        anonymous_label=SpeakerLabel.anonymous(command.anonymous_label),
        named_label=SpeakerLabel.named(participant.display_name),
        participant_id=participant.id,
        confidence=command.confidence,
        source=SpeakerMappingSource.MANUAL,
        status=SpeakerMappingStatus.CONFIRMED,
    )


def _mapping_records(
    *,
    job_id: ProcessingJobId,
    transcript_id: TranscriptId,
    mappings: tuple[SpeakerMapping, ...],
    warning_count: int,
) -> tuple[SpeakerMappingRecord, ...]:
    return tuple(
        SpeakerMappingRecord(
            job_id=job_id,
            transcript_id=transcript_id,
            mapping=mapping,
            diagnostics={"warning_count": warning_count},
        )
        for mapping in mappings
    )
