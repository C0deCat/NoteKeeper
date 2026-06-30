"""Generate recap use case."""

from notekeeper.application.commands import GenerateRecapCommand
from notekeeper.application.ports import (
    IdGenerator,
    RecapGenerator,
    RecapRepository,
    Tokenizer,
    TranscriptRepository,
)
from notekeeper.application.results import GenerateRecapResult
from notekeeper.application.use_cases._recaps import generate_recap_for_transcript
from notekeeper.application.use_cases.utils import _require_transcript
from notekeeper.domain import TranscriptId


class GenerateRecap:
    def __init__(
        self,
        transcript_repository: TranscriptRepository,
        recap_repository: RecapRepository,
        tokenizer: Tokenizer,
        recap_generator: RecapGenerator,
        id_generator: IdGenerator,
    ) -> None:
        self._transcript_repository = transcript_repository
        self._recap_repository = recap_repository
        self._tokenizer = tokenizer
        self._recap_generator = recap_generator
        self._id_generator = id_generator

    def execute(self, command: GenerateRecapCommand) -> GenerateRecapResult:
        transcript = _require_transcript(
            self._transcript_repository,
            TranscriptId(command.transcript_id),
        )
        recap = generate_recap_for_transcript(
            transcript,
            id_generator=self._id_generator,
            tokenizer=self._tokenizer,
            recap_generator=self._recap_generator,
            recap_repository=self._recap_repository,
        )
        return GenerateRecapResult(recap=recap)
