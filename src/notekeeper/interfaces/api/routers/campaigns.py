"""Campaign HTTP routes."""

from fastapi import APIRouter, Request, Response, status

from notekeeper.application import (
    CreateCampaignCommand,
    DeleteCampaignCommand,
    GetCampaignCommand,
    ListCampaignsCommand,
    UpdateCampaignCommand,
)

from ..dependencies import WorkspaceSession
from ..mappers import campaign_response
from ..openapi import ERROR_RESPONSES
from ..schemas import (
    CampaignPatchRequest,
    CampaignRequest,
    CampaignResponse,
    ItemsResponse,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/campaigns",
    tags=["campaigns"],
)


@router.get(
    "",
    response_model=ItemsResponse[CampaignResponse],
    responses=ERROR_RESPONSES,
    operation_id="list_campaigns",
)
def list_campaigns(session: WorkspaceSession) -> ItemsResponse[CampaignResponse]:
    result = session.use_cases.campaigns.list.execute(ListCampaignsCommand())
    return ItemsResponse(items=[campaign_response(value) for value in result.campaigns])


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
    operation_id="create_campaign",
)
def create_campaign(
    payload: CampaignRequest,
    request: Request,
    response: Response,
    session: WorkspaceSession,
) -> CampaignResponse:
    result = session.use_cases.campaigns.create.execute(
        CreateCampaignCommand(name=payload.name)
    )
    response.headers["Location"] = str(
        request.url_for(
            "get_campaign",
            workspace_id=str(session.access.workspace_id),
            campaign_id=str(result.campaign.id),
        )
    )
    return campaign_response(result.campaign)


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
    responses=ERROR_RESPONSES,
    operation_id="get_campaign",
)
def get_campaign(campaign_id: str, session: WorkspaceSession) -> CampaignResponse:
    result = session.use_cases.campaigns.get.execute(
        GetCampaignCommand(campaign_id=campaign_id)
    )
    return campaign_response(result.campaign)


@router.patch(
    "/{campaign_id}",
    response_model=CampaignResponse,
    responses=ERROR_RESPONSES,
    operation_id="update_campaign",
)
def update_campaign(
    campaign_id: str,
    payload: CampaignPatchRequest,
    session: WorkspaceSession,
) -> CampaignResponse:
    result = session.use_cases.campaigns.update.execute(
        UpdateCampaignCommand(campaign_id=campaign_id, name=payload.name)
    )
    return campaign_response(result.campaign)


@router.delete(
    "/{campaign_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
    operation_id="delete_campaign",
)
def delete_campaign(campaign_id: str, session: WorkspaceSession) -> Response:
    session.use_cases.campaigns.delete.execute(
        DeleteCampaignCommand(campaign_id=campaign_id, delete_files=False)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
