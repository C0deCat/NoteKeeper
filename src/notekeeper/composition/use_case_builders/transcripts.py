"""Transcript use-case group builder."""

from notekeeper.application import (
    ExportTranscriptMarkdown,
    PreviewTranscriptMarkdown,
    TranscriptUseCases,
)

from .wiring_context import UseCaseWiringContext


def build_transcript_use_cases(context: UseCaseWiringContext) -> TranscriptUseCases:
    return TranscriptUseCases(
        preview_markdown=PreviewTranscriptMarkdown(
            context.repositories.transcript_repository
        ),
        export_markdown=ExportTranscriptMarkdown(
            context.repositories.transcript_repository,
            context.services.artifact_storage,
        ),
    )


__all__ = ["build_transcript_use_cases"]
