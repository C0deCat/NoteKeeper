"""Campaign participant HTTP routes."""

from fastapi import APIRouter, Request, Response, status

from notekeeper.application import (
    AddParticipantToCampaignCommand,
    DeleteParticipantCommand,
    ListParticipantsCommand,
    UpdateParticipantCommand,
)

from ..dependencies import WorkspaceSession
from ..mappers import participant_response
from ..openapi import ERROR_RESPONSES
from ..schemas import (
    ItemsResponse,
    ParticipantPatchRequest,
    ParticipantRequest,
    ParticipantResponse,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/participants",
    tags=["participants"],
)


@router.get(
    "",
    response_model=ItemsResponse[ParticipantResponse],
    responses=ERROR_RESPONSES,
    operation_id="list_participants",
)
def list_participants(
    campaign_id: str,
    session: WorkspaceSession,
) -> ItemsResponse[ParticipantResponse]:
    result = session.use_cases.participants.list.execute(
        ListParticipantsCommand(campaign_id=campaign_id)
    )
    return ItemsResponse(
        items=[participant_response(value) for value in result.participants]
    )


@router.post(
    "",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
    operation_id="create_participant",
)
def create_participant(
    campaign_id: str,
    payload: ParticipantRequest,
    request: Request,
    response: Response,
    session: WorkspaceSession,
) -> ParticipantResponse:
    result = session.use_cases.participants.add.execute(
        AddParticipantToCampaignCommand(
            campaign_id=campaign_id,
            display_name=payload.display_name,
        )
    )
    response.headers["Location"] = str(
        request.url_for(
            "update_participant",
            workspace_id=str(session.access.workspace_id),
            campaign_id=campaign_id,
            participant_id=str(result.participant.id),
        )
    )
    return participant_response(result.participant)


@router.patch(
    "/{participant_id}",
    response_model=ParticipantResponse,
    responses=ERROR_RESPONSES,
    operation_id="update_participant",
)
def update_participant(
    campaign_id: str,
    participant_id: str,
    payload: ParticipantPatchRequest,
    session: WorkspaceSession,
) -> ParticipantResponse:
    result = session.use_cases.participants.update.execute(
        UpdateParticipantCommand(
            campaign_id=campaign_id,
            participant_id=participant_id,
            display_name=payload.display_name,
        )
    )
    return participant_response(result.participant)


@router.delete(
    "/{participant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
    operation_id="delete_participant",
)
def delete_participant(
    campaign_id: str,
    participant_id: str,
    session: WorkspaceSession,
) -> Response:
    session.use_cases.participants.delete.execute(
        DeleteParticipantCommand(
            campaign_id=campaign_id,
            participant_id=participant_id,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
