"""Export transcript markdown use case."""

from notekeeper.application.commands import ExportTranscriptMarkdownCommand
from notekeeper.application.ports import ArtifactStorage, TranscriptRepository
from notekeeper.application.results import ExportMarkdownResult
from notekeeper.application.use_cases.export._markdown import (
    render_transcript_markdown,
)
from notekeeper.application.use_cases.utils import _require_transcript
from notekeeper.domain import TranscriptId


class ExportTranscriptMarkdown:
    def __init__(
        self,
        transcript_repository: TranscriptRepository,
        artifact_storage: ArtifactStorage,
    ) -> None:
        self._transcript_repository = transcript_repository
        self._artifact_storage = artifact_storage

    def execute(
        self,
        command: ExportTranscriptMarkdownCommand,
    ) -> ExportMarkdownResult:
        transcript = _require_transcript(
            self._transcript_repository,
            TranscriptId(command.transcript_id),
        )
        artifact = self._artifact_storage.save_text(
            suggested_name=f"transcript-{transcript.id}.md",
            content=render_transcript_markdown(transcript),
            media_type="text/markdown",
        )
        return ExportMarkdownResult(artifact=artifact)
