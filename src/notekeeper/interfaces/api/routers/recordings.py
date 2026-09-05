"""Multipart recording HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, Response, UploadFile, status

from notekeeper.application import (
    DeleteAudioTrackCommand,
    ListAudioTracksCommand,
    SubmitRecordingForProcessingCommand,
)

from ..dependencies import RuntimeDependency, WorkspaceSession
from ..mappers import job_response, recording_response
from ..openapi import ERROR_RESPONSES
from ..schemas import (
    ItemsResponse,
    RecordingResponse,
    RecordingSubmissionResponse,
)
from ..utils import remove_temporary_upload, save_audio_upload

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/recordings",
    tags=["recordings"],
)


@router.get(
    "",
    response_model=ItemsResponse[RecordingResponse],
    responses=ERROR_RESPONSES,
    operation_id="list_recordings",
)
def list_recordings(
    campaign_id: str,
    session: WorkspaceSession,
) -> ItemsResponse[RecordingResponse]:
    result = session.use_cases.recordings.list.execute(
        ListAudioTracksCommand(campaign_id=campaign_id)
    )
    return ItemsResponse(
        items=[recording_response(value) for value in result.audio_tracks]
    )


@router.post(
    "",
    response_model=RecordingSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
    operation_id="create_recording",
)
def create_recording(
    campaign_id: str,
    request: Request,
    response: Response,
    session: WorkspaceSession,
    runtime: RuntimeDependency,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
) -> RecordingSubmissionResponse:
    path = save_audio_upload(
        file,
        directory=runtime.upload_directory,
        allowed_extensions=runtime.audio_extensions,
        max_bytes=runtime.upload_max_bytes,
    )
    try:
        result = session.use_cases.recordings.submit_for_processing.execute(
            SubmitRecordingForProcessingCommand(
                campaign_id=campaign_id,
                title=title,
                source_path=str(path),
            )
        )
    finally:
        remove_temporary_upload(path)
    response.headers["Location"] = str(
        request.url_for(
            "delete_recording",
            workspace_id=str(session.access.workspace_id),
            campaign_id=campaign_id,
            recording_id=str(result.audio_track.id),
        )
    )
    return RecordingSubmissionResponse(
        recording=recording_response(result.audio_track),
        job=job_response(result.job),
    )


@router.delete(
    "/{recording_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
    operation_id="delete_recording",
)
def delete_recording(
    campaign_id: str,
    recording_id: str,
    session: WorkspaceSession,
) -> Response:
    session.use_cases.recordings.delete.execute(
        DeleteAudioTrackCommand(
            campaign_id=campaign_id,
            audio_track_id=recording_id,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
