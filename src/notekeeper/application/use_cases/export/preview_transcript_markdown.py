"""Preview transcript Markdown use case."""

from notekeeper.application.commands import PreviewTranscriptMarkdownCommand
from notekeeper.application.results import MarkdownPreviewResult
from notekeeper.application.use_cases.export._markdown import (
    render_transcript_markdown,
)
from notekeeper.application.use_cases.utils import _require_transcript
from notekeeper.application.ports import TranscriptRepository
from notekeeper.domain import TranscriptId


class PreviewTranscriptMarkdown:
    def __init__(self, transcript_repository: TranscriptRepository) -> None:
        self._transcript_repository = transcript_repository

    def execute(
        self,
        command: PreviewTranscriptMarkdownCommand,
    ) -> MarkdownPreviewResult:
        transcript = _require_transcript(
            self._transcript_repository,
            TranscriptId(command.transcript_id),
        )
        return MarkdownPreviewResult(markdown=render_transcript_markdown(transcript))
