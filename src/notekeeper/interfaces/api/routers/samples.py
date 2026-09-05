"""Multipart voice-sample HTTP routes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, Response, UploadFile, status

from notekeeper.application import (
    AddVoiceSampleCommand,
    DeleteVoiceSampleCommand,
    ListVoiceSamplesCommand,
)

from ..dependencies import RuntimeDependency, WorkspaceSession
from ..mappers import voice_sample_response
from ..openapi import ERROR_RESPONSES
from ..schemas import ItemsResponse, VoiceSampleResponse
from ..utils import remove_temporary_upload, save_audio_upload

router = APIRouter(tags=["voice-samples"])
_BASE = "/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}"


@router.get(
    _BASE + "/participants/{participant_id}/voice-samples",
    response_model=ItemsResponse[VoiceSampleResponse],
    responses=ERROR_RESPONSES,
    operation_id="list_voice_samples",
)
def list_voice_samples(
    campaign_id: str,
    participant_id: str,
    session: WorkspaceSession,
) -> ItemsResponse[VoiceSampleResponse]:
    result = session.use_cases.samples.list.execute(
        ListVoiceSamplesCommand(
            campaign_id=campaign_id,
            participant_id=participant_id,
        )
    )
    return ItemsResponse(
        items=[voice_sample_response(value) for value in result.voice_samples]
    )


@router.post(
    _BASE + "/participants/{participant_id}/voice-samples",
    response_model=VoiceSampleResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
    operation_id="create_voice_sample",
)
def create_voice_sample(
    campaign_id: str,
    participant_id: str,
    request: Request,
    response: Response,
    session: WorkspaceSession,
    runtime: RuntimeDependency,
    file: Annotated[UploadFile, File()],
    recorded_at: Annotated[datetime | None, Form()] = None,
) -> VoiceSampleResponse:
    path = save_audio_upload(
        file,
        directory=runtime.upload_directory,
        allowed_extensions=runtime.audio_extensions,
        max_bytes=runtime.upload_max_bytes,
    )
    try:
        result = session.use_cases.samples.add.execute(
            AddVoiceSampleCommand(
                campaign_id=campaign_id,
                participant_id=participant_id,
                source_path=str(path),
                recorded_at=recorded_at,
            )
        )
    finally:
        remove_temporary_upload(path)
    response.headers["Location"] = str(
        request.url_for(
            "delete_voice_sample",
            workspace_id=str(session.access.workspace_id),
            campaign_id=campaign_id,
            sample_id=str(result.voice_sample.id),
        )
    )
    return voice_sample_response(result.voice_sample)


@router.delete(
    _BASE + "/voice-samples/{sample_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
    operation_id="delete_voice_sample",
)
def delete_voice_sample(
    campaign_id: str,
    sample_id: str,
    session: WorkspaceSession,
) -> Response:
    session.use_cases.samples.delete.execute(
        DeleteVoiceSampleCommand(
            campaign_id=campaign_id,
            voice_sample_id=sample_id,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
