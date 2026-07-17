"""Run processing job use case."""

import logging
from dataclasses import replace

from notekeeper.application.commands import RunProcessingJobCommand
from notekeeper.application.errors import InvalidOperationError, PortExecutionError
from notekeeper.application.ports import (
    AudioProcessor,
    AudioTrackRepository,
    CampaignRepository,
    Clock,
    IdGenerator,
    JobRepository,
    RecapGenerator,
    RecapRepository,
    SpeakerIdentifier,
    SpeakerMappingRepository,
    Tokenizer,
    Transcriber,
    TranscriptRepository,
)
from notekeeper.application.results import (
    PreparedAudioResult,
    RunProcessingJobResult,
    SpeakerMappingRecord,
)
from notekeeper.application.use_cases._recaps import generate_recap_for_transcript
from notekeeper.application.use_cases.utils import (
    _require_audio_track,
    _require_campaign,
    _require_job,
)
from notekeeper.domain import (
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
    SpeakerMapping,
    TranscriptId,
    apply_speaker_mappings,
)


logger = logging.getLogger(__name__)


class RunProcessingJob:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        audio_track_repository: AudioTrackRepository,
        transcript_repository: TranscriptRepository,
        recap_repository: RecapRepository,
        job_repository: JobRepository,
        audio_processor: AudioProcessor,
        transcriber: Transcriber,
        speaker_identifier: SpeakerIdentifier,
        speaker_mapping_repository: SpeakerMappingRepository,
        tokenizer: Tokenizer,
        recap_generator: RecapGenerator,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._audio_track_repository = audio_track_repository
        self._transcript_repository = transcript_repository
        self._recap_repository = recap_repository
        self._job_repository = job_repository
        self._audio_processor = audio_processor
        self._transcriber = transcriber
        self._speaker_identifier = speaker_identifier
        self._speaker_mapping_repository = speaker_mapping_repository
        self._tokenizer = tokenizer
        self._recap_generator = recap_generator
        self._clock = clock
        self._id_generator = id_generator

    def execute(self, command: RunProcessingJobCommand) -> RunProcessingJobResult:
        running_job = self.start(command)
        return self.execute_running(command, running_job=running_job)

    def start(self, command: RunProcessingJobCommand) -> ProcessingJob:
        job = _require_job(self._job_repository, ProcessingJobId(command.job_id))
        if job.status is not JobStatus.PENDING:
            raise InvalidOperationError("processing job must be pending")

        campaign = _require_campaign(self._campaign_repository, job.campaign_id)
        audio_track = _require_audio_track(
            self._audio_track_repository,
            job.audio_track_id,
        )

        running_job = replace(
            job,
            status=JobStatus.RUNNING,
            updated_at=self._clock.now(),
            warnings=(),
            error_message=None,
        )
        save_if_status = getattr(self._job_repository, "save_if_status", None)
        if callable(save_if_status):
            if not save_if_status(running_job, JobStatus.PENDING):
                raise InvalidOperationError("processing job is no longer pending")
        else:
            self._job_repository.save(running_job)
        return running_job

    def execute_running(
        self,
        command: RunProcessingJobCommand,
        *,
        running_job: ProcessingJob | None = None,
    ) -> RunProcessingJobResult:
        running_job = running_job or _require_job(
            self._job_repository,
            ProcessingJobId(command.job_id),
        )
        if running_job.status is not JobStatus.RUNNING:
            raise InvalidOperationError("processing job must be running")

        campaign = _require_campaign(
            self._campaign_repository,
            running_job.campaign_id,
        )
        audio_track = _require_audio_track(
            self._audio_track_repository,
            running_job.audio_track_id,
        )
        job = running_job

        persisted_transcript = None
        known_warnings = ()
        try:
            prepared_audio = self._audio_processor.prepare_session_audio(
                audio_track,
                campaign.voice_samples,
                job_id=job.id,
            )
            raw_transcript = self._transcriber.transcribe(
                prepared_audio.audio_artifact,
                transcript_id=TranscriptId(self._id_generator.transcript_id()),
                campaign_id=campaign.id,
                audio_track_id=audio_track.id,
            )
            mappings = self._speaker_identifier.identify(
                campaign,
                raw_transcript,
                prepared_audio=prepared_audio,
            )
            mapped = apply_speaker_mappings(campaign, raw_transcript, mappings)
            known_warnings = mapped.warnings
            self._transcript_repository.save(mapped.transcript)
            persisted_transcript = mapped.transcript
            self._speaker_mapping_repository.save_many(
                _mapping_records(
                    job_id=job.id,
                    transcript_id=mapped.transcript.id,
                    mappings=mappings,
                    prepared_audio=prepared_audio,
                ),
            )

            if mapped.warnings:
                waiting_job = replace(
                    running_job,
                    status=JobStatus.WAITING_FOR_REVIEW,
                    updated_at=self._clock.now(),
                    transcript_id=mapped.transcript.id,
                    warnings=mapped.warnings,
                )
                waiting_job = self._save_terminal(waiting_job)
                return RunProcessingJobResult(
                    job=waiting_job,
                    transcript=mapped.transcript,
                    recap=None,
                    warnings=mapped.warnings,
                )

            recap = generate_recap_for_transcript(
                mapped.transcript,
                id_generator=self._id_generator,
                tokenizer=self._tokenizer,
                recap_generator=self._recap_generator,
                recap_repository=self._recap_repository,
                job_id=job.id,
            )
            completed_job = replace(
                running_job,
                status=JobStatus.COMPLETED,
                updated_at=self._clock.now(),
                transcript_id=mapped.transcript.id,
                recap_id=recap.id,
                warnings=(),
            )
            completed_job = self._save_terminal(completed_job)
            return RunProcessingJobResult(
                job=completed_job,
                transcript=mapped.transcript,
                recap=recap,
                warnings=(),
            )
        except PortExecutionError as exc:
            logger.exception(
                "Processing job failed job_id=%s campaign_id=%s audio_track_id=%s",
                job.id,
                campaign.id,
                audio_track.id,
            )
            failed_job = replace(
                running_job,
                status=JobStatus.FAILED,
                updated_at=self._clock.now(),
                transcript_id=(
                    persisted_transcript.id
                    if persisted_transcript is not None
                    else None
                ),
                warnings=known_warnings,
                error_message=_port_error_message(exc),
            )
            failed_job = self._save_terminal(failed_job)
            return RunProcessingJobResult(
                job=failed_job,
                transcript=persisted_transcript,
                recap=None,
                warnings=known_warnings,
            )

    def _save_terminal(self, job: ProcessingJob) -> ProcessingJob:
        save_if_status = getattr(self._job_repository, "save_if_status", None)
        if callable(save_if_status):
            if save_if_status(job, JobStatus.RUNNING):
                return job
            current = _require_job(self._job_repository, job.id)
            if current.status is JobStatus.CANCELED:
                return current
            raise InvalidOperationError("processing job status changed during execution")
        self._job_repository.save(job)
        return job


def _port_error_message(error: PortExecutionError) -> str:
    message = str(error).strip()
    return message if message else type(error).__name__


def _mapping_records(
    *,
    job_id: ProcessingJobId,
    transcript_id: TranscriptId,
    mappings: tuple[SpeakerMapping, ...],
    prepared_audio: PreparedAudioResult,
) -> tuple[SpeakerMappingRecord, ...]:
    diagnostics = {
        "prepared_audio_artifact_uri": prepared_audio.audio_artifact.uri,
        "prepared_audio_manifest_uri": prepared_audio.manifest_artifact.uri,
        "voice_sample_range_count": len(prepared_audio.voice_sample_ranges),
    }
    return tuple(
        SpeakerMappingRecord(
            job_id=job_id,
            transcript_id=transcript_id,
            mapping=mapping,
            diagnostics=diagnostics,
        )
        for mapping in mappings
    )
