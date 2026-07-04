"""Run processing job use case."""

from dataclasses import replace

from notekeeper.application.commands import RunProcessingJobCommand
from notekeeper.application.errors import InvalidOperationError
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
    ProcessingJobId,
    SpeakerMapping,
    TranscriptId,
    apply_speaker_mappings,
)


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
        self._job_repository.save(running_job)

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
        self._transcript_repository.save(mapped.transcript)
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
            self._job_repository.save(waiting_job)
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
        self._job_repository.save(completed_job)
        return RunProcessingJobResult(
            job=completed_job,
            transcript=mapped.transcript,
            recap=recap,
            warnings=(),
        )


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
