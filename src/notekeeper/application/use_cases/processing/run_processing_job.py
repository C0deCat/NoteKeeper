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
    ProgressTracker,
    ProgressTrackerFactory,
    RecapGenerator,
    RecapGuidances,
    RecapRepository,
    SpeakerIdentifier,
    SpeakerMappingRepository,
    SpeakerReviewSubmissionRepository,
    Tokenizer,
    Transcriber,
    TranscriptRepository,
    TransientAudioCleaner,
)
from notekeeper.application.results import RunProcessingJobResult
from notekeeper.application.use_cases._recaps import generate_recap_for_transcript
from notekeeper.application.use_cases.utils import (
    require_audio_track,
    require_campaign,
    require_job,
)
from notekeeper.domain import (
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
    ProcessingStage,
    TranscriptId,
    apply_speaker_mappings,
)

from .job_transitions import claim_queued_job, save_terminal_job
from .mapping_records import (
    build_automatic_mapping_records,
    build_review_mapping_records,
)
from .progress_outcomes import complete_or_cancel, fail_or_cancel, pause_or_cancel

logger = logging.getLogger(__name__)


class ExecuteQueuedProcessingJob:
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
        speaker_review_submission_repository: SpeakerReviewSubmissionRepository,
        tokenizer: Tokenizer,
        recap_guidances: RecapGuidances,
        recap_generator: RecapGenerator,
        clock: Clock,
        id_generator: IdGenerator,
        *,
        progress_tracker_factory: ProgressTrackerFactory | None = None,
        progress_stages: tuple[ProcessingStage, ...] = (),
        transient_audio_cleaner: TransientAudioCleaner | None = None,
        target_token_count: int = 30_000,
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
        self._speaker_review_submission_repository = (
            speaker_review_submission_repository
        )
        self._tokenizer = tokenizer
        self._recap_guidances = recap_guidances
        self._recap_generator = recap_generator
        self._clock = clock
        self._id_generator = id_generator
        self._progress_tracker_factory = progress_tracker_factory
        self._progress_stages = progress_stages
        self._transient_audio_cleaner = transient_audio_cleaner
        self._target_token_count = target_token_count

    def execute(self, command: RunProcessingJobCommand) -> RunProcessingJobResult:
        running_job = self.start(command)
        return self.execute_running(command, running_job=running_job)

    def start(self, command: RunProcessingJobCommand) -> ProcessingJob:
        job = require_job(self._job_repository, ProcessingJobId(command.job_id))
        if job.status is not JobStatus.QUEUED:
            raise InvalidOperationError("processing job must be queued")

        running_job = replace(
            job,
            status=JobStatus.RUNNING,
            updated_at=self._clock.now(),
            warnings=(),
            error_message=None,
        )
        claim_queued_job(self._job_repository, running_job)
        return running_job

    def execute_running(
        self,
        command: RunProcessingJobCommand,
        *,
        running_job: ProcessingJob | None = None,
    ) -> RunProcessingJobResult:
        running_job = running_job or require_job(
            self._job_repository,
            ProcessingJobId(command.job_id),
        )
        if running_job.status is not JobStatus.RUNNING:
            raise InvalidOperationError("processing job must be running")

        if running_job.transcript_id is not None:
            return self._execute_review_continuation(running_job)

        campaign = require_campaign(
            self._campaign_repository,
            running_job.campaign_id,
        )
        audio_track = require_audio_track(
            self._audio_track_repository,
            running_job.audio_track_id,
        )
        job = running_job
        progress = self._create_progress(job.id)

        persisted_transcript = None
        known_warnings = ()
        try:
            audio_progress = {"progress": progress} if progress is not None else {}
            prepared_audio = self._audio_processor.prepare_session_audio(
                audio_track,
                campaign.voice_samples,
                job_id=job.id,
                **audio_progress,
            )
            transcription_progress = (
                {"progress": progress} if progress is not None else {}
            )
            raw_transcript = self._transcriber.transcribe(
                prepared_audio.audio_artifact,
                transcript_id=TranscriptId(self._id_generator.transcript_id()),
                campaign_id=campaign.id,
                audio_track_id=audio_track.id,
                **transcription_progress,
            )
            if progress is not None:
                progress.start_stage(
                    ProcessingStage.MAPPING_SPEAKERS,
                    timing_available=False,
                )
            mappings = self._speaker_identifier.identify(
                campaign,
                raw_transcript,
                prepared_audio=prepared_audio,
            )
            mapped = apply_speaker_mappings(campaign, raw_transcript, mappings)
            if progress is not None:
                progress.complete_stage()
            known_warnings = mapped.warnings
            self._transcript_repository.save(mapped.transcript)
            persisted_transcript = mapped.transcript
            self._speaker_mapping_repository.save_many(
                build_automatic_mapping_records(
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
                waiting_job = save_terminal_job(self._job_repository, waiting_job)
                if progress is not None:
                    pause_or_cancel(progress, waiting_job)
                return RunProcessingJobResult(
                    job=waiting_job,
                    transcript=mapped.transcript,
                    recap=None,
                    warnings=mapped.warnings,
                )

            if progress is not None:
                progress.start_stage(
                    ProcessingStage.GENERATING_RECAP,
                    timing_available=True,
                )
            recap = generate_recap_for_transcript(
                mapped.transcript,
                id_generator=self._id_generator,
                tokenizer=self._tokenizer,
                recap_guidances=self._recap_guidances,
                recap_generator=self._recap_generator,
                recap_repository=self._recap_repository,
                job_id=job.id,
                progress_callback=(
                    progress.update_fraction if progress is not None else None
                ),
                target_token_count=self._target_token_count,
            )
            if progress is not None:
                progress.complete_stage()
            completed_job = replace(
                running_job,
                status=JobStatus.COMPLETED,
                updated_at=self._clock.now(),
                transcript_id=mapped.transcript.id,
                recap_id=recap.id,
                warnings=(),
            )
            completed_job = save_terminal_job(self._job_repository, completed_job)
            if progress is not None:
                complete_or_cancel(progress, completed_job)
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
            failed_job = save_terminal_job(self._job_repository, failed_job)
            if progress is not None:
                fail_or_cancel(progress, failed_job)
            return RunProcessingJobResult(
                job=failed_job,
                transcript=persisted_transcript,
                recap=None,
                warnings=known_warnings,
            )
        except Exception:
            if progress is not None:
                progress.fail()
            raise
        finally:
            if progress is not None:
                progress.close()
            if self._transient_audio_cleaner is not None:
                try:
                    self._transient_audio_cleaner.clean(campaign.id, job.id)
                except Exception:
                    logger.exception(
                        "Could not clean transient audio job_id=%s campaign_id=%s",
                        job.id,
                        campaign.id,
                    )

    def _create_progress(
        self,
        job_id: ProcessingJobId,
    ) -> ProgressTracker | None:
        if self._progress_tracker_factory is None or not self._progress_stages:
            return None
        return self._progress_tracker_factory.create(
            str(job_id),
            self._progress_stages,
        )

    def _execute_review_continuation(
        self,
        running_job: ProcessingJob,
    ) -> RunProcessingJobResult:
        transcript_id = running_job.transcript_id
        if transcript_id is None:
            raise InvalidOperationError("review continuation requires a transcript")
        submission = self._speaker_review_submission_repository.get(running_job.id)
        if submission is None:
            raise InvalidOperationError("queued review submission was not found")
        campaign = require_campaign(
            self._campaign_repository,
            running_job.campaign_id,
        )
        transcript = self._transcript_repository.get(transcript_id)
        if transcript is None:
            raise InvalidOperationError("review transcript was not found")
        progress = (
            self._progress_tracker_factory.create(
                str(running_job.id),
                (
                    ProcessingStage.MAPPING_SPEAKERS,
                    ProcessingStage.GENERATING_RECAP,
                ),
            )
            if self._progress_tracker_factory is not None
            else None
        )
        known_warnings = ()
        try:
            if progress is not None:
                progress.start_stage(
                    ProcessingStage.MAPPING_SPEAKERS,
                    timing_available=False,
                )
            mapped = apply_speaker_mappings(
                campaign,
                transcript,
                submission.mappings,
            )
            known_warnings = mapped.warnings
            self._transcript_repository.save(mapped.transcript)
            self._speaker_mapping_repository.save_many(
                build_review_mapping_records(
                    job_id=running_job.id,
                    transcript_id=mapped.transcript.id,
                    mappings=submission.mappings,
                    warning_count=len(mapped.warnings),
                )
            )
            if progress is not None:
                progress.complete_stage()
            if mapped.warnings:
                waiting_job = replace(
                    running_job,
                    status=JobStatus.WAITING_FOR_REVIEW,
                    updated_at=self._clock.now(),
                    transcript_id=mapped.transcript.id,
                    warnings=mapped.warnings,
                )
                waiting_job = save_terminal_job(self._job_repository, waiting_job)
                if progress is not None:
                    pause_or_cancel(progress, waiting_job)
                return RunProcessingJobResult(
                    job=waiting_job,
                    transcript=mapped.transcript,
                    recap=None,
                    warnings=mapped.warnings,
                )
            if progress is not None:
                progress.start_stage(
                    ProcessingStage.GENERATING_RECAP,
                    timing_available=True,
                )
            recap = generate_recap_for_transcript(
                mapped.transcript,
                id_generator=self._id_generator,
                tokenizer=self._tokenizer,
                recap_guidances=self._recap_guidances,
                recap_generator=self._recap_generator,
                recap_repository=self._recap_repository,
                job_id=running_job.id,
                progress_callback=(
                    progress.update_fraction if progress is not None else None
                ),
                target_token_count=self._target_token_count,
            )
            if progress is not None:
                progress.complete_stage()
            completed_job = replace(
                running_job,
                status=JobStatus.COMPLETED,
                updated_at=self._clock.now(),
                transcript_id=mapped.transcript.id,
                recap_id=recap.id,
                warnings=(),
            )
            completed_job = save_terminal_job(self._job_repository, completed_job)
            if progress is not None:
                complete_or_cancel(progress, completed_job)
            return RunProcessingJobResult(
                job=completed_job,
                transcript=mapped.transcript,
                recap=recap,
                warnings=(),
            )
        except PortExecutionError as exc:
            failed_job = replace(
                running_job,
                status=JobStatus.FAILED,
                updated_at=self._clock.now(),
                transcript_id=transcript.id,
                warnings=known_warnings,
                error_message=_port_error_message(exc),
            )
            failed_job = save_terminal_job(self._job_repository, failed_job)
            if progress is not None:
                fail_or_cancel(progress, failed_job)
            return RunProcessingJobResult(
                job=failed_job,
                transcript=transcript,
                recap=None,
                warnings=known_warnings,
            )
        finally:
            self._speaker_review_submission_repository.delete(running_job.id)
            if progress is not None:
                progress.close()


def _port_error_message(error: PortExecutionError) -> str:
    message = str(error).strip()
    return message if message else type(error).__name__


RunProcessingJob = ExecuteQueuedProcessingJob

__all__ = ["ExecuteQueuedProcessingJob", "RunProcessingJob"]
