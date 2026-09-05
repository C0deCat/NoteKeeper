"""Authorized transcript and recap Markdown routes."""

from fastapi import APIRouter

from notekeeper.application import (
    PreviewRecapMarkdownCommand,
    PreviewTranscriptMarkdownCommand,
)

from ..dependencies import WorkspaceSession
from ..openapi import ERROR_RESPONSES
from ..schemas import MarkdownResponse

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}",
    tags=["results"],
)


@router.get(
    "/transcripts/{transcript_id}",
    response_model=MarkdownResponse,
    responses=ERROR_RESPONSES,
    operation_id="get_transcript",
)
def get_transcript(
    transcript_id: str,
    session: WorkspaceSession,
) -> MarkdownResponse:
    result = session.use_cases.transcripts.preview_markdown.execute(
        PreviewTranscriptMarkdownCommand(transcript_id=transcript_id)
    )
    return MarkdownResponse(id=transcript_id, markdown=result.markdown)


@router.get(
    "/recaps/{recap_id}",
    response_model=MarkdownResponse,
    responses=ERROR_RESPONSES,
    operation_id="get_recap",
)
def get_recap(recap_id: str, session: WorkspaceSession) -> MarkdownResponse:
    result = session.use_cases.recaps.preview_markdown.execute(
        PreviewRecapMarkdownCommand(recap_id=recap_id)
    )
    return MarkdownResponse(id=recap_id, markdown=result.markdown)


__all__ = ["router"]
