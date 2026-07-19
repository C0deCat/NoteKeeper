"""Generate recap use case."""

from dataclasses import replace

from notekeeper.application.commands import GenerateRecapCommand
from notekeeper.application.errors import InvalidOperationError
from notekeeper.application.ports import (
    Clock,
    IdGenerator,
    JobRepository,
    RecapGenerator,
    RecapRepository,
    Tokenizer,
    TranscriptRepository,
)
from notekeeper.application.results import GenerateRecapResult
from notekeeper.application.use_cases._recaps import generate_recap_for_transcript
from notekeeper.application.use_cases.utils import _require_job, _require_transcript
from notekeeper.domain import ProcessingJobId


class GenerateRecap:
    def __init__(
        self,
        job_repository: JobRepository,
        transcript_repository: TranscriptRepository,
        recap_repository: RecapRepository,
        tokenizer: Tokenizer,
        recap_generator: RecapGenerator,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self._job_repository = job_repository
        self._transcript_repository = transcript_repository
        self._recap_repository = recap_repository
        self._tokenizer = tokenizer
        self._recap_generator = recap_generator
        self._clock = clock
        self._id_generator = id_generator

    def execute(self, command: GenerateRecapCommand) -> GenerateRecapResult:
        job = _require_job(
            self._job_repository,
            ProcessingJobId(command.job_id),
        )
        if job.transcript_id is None:
            raise InvalidOperationError("processing job has no transcript")
        transcript = _require_transcript(
            self._transcript_repository,
            job.transcript_id,
        )
        recap = generate_recap_for_transcript(
            transcript,
            id_generator=self._id_generator,
            tokenizer=self._tokenizer,
            recap_generator=self._recap_generator,
            recap_repository=self._recap_repository,
            job_id=job.id,
        )
        updated_job = replace(
            job,
            recap_id=recap.id,
            updated_at=self._clock.now(),
        )
        self._job_repository.save(updated_job)
        return GenerateRecapResult(job=updated_job, recap=recap)
