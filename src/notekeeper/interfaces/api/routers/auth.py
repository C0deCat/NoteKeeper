"""Provider-neutral authentication and identity routes."""

from fastapi import APIRouter, Request, Response, status

from ..dependencies import CurrentUser, PersonalSession, RuntimeDependency
from ..openapi import ERROR_RESPONSES
from ..schemas import (
    CredentialsRequest,
    ItemsResponse,
    MeResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
    WorkspaceResponse,
)

router = APIRouter(prefix="/api/v1", tags=["identity"])


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
    operation_id="register",
)
def register(
    payload: CredentialsRequest,
    runtime: RuntimeDependency,
    request: Request,
    response: Response,
) -> TokenResponse:
    grant = runtime.register(payload.login, payload.password)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Location"] = str(request.url_for("get_me"))
    return _token_response(grant)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    responses=ERROR_RESPONSES,
    operation_id="login",
)
def login(
    payload: CredentialsRequest,
    runtime: RuntimeDependency,
    response: Response,
) -> TokenResponse:
    grant = runtime.login(payload.login, payload.password)
    response.headers["Cache-Control"] = "no-store"
    return _token_response(grant)


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    responses=ERROR_RESPONSES,
    operation_id="refresh_session",
)
def refresh_session(
    payload: RefreshTokenRequest,
    runtime: RuntimeDependency,
    response: Response,
) -> TokenResponse:
    grant = runtime.refresh(payload.refresh_token)
    response.headers["Cache-Control"] = "no-store"
    return _token_response(grant)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
    operation_id="logout",
)
def logout(payload: RefreshTokenRequest, runtime: RuntimeDependency) -> Response:
    runtime.logout(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=MeResponse,
    responses=ERROR_RESPONSES,
    operation_id="get_me",
)
def get_me(user: CurrentUser, session: PersonalSession) -> MeResponse:
    settings = session.use_cases.settings
    default_workspace_id = None
    if settings is not None:
        value = settings.get_user().default_workspace_id
        default_workspace_id = str(value) if value is not None else None
    return MeResponse(
        user_id=str(user.id),
        login=user.login,
        default_workspace_id=default_workspace_id,
    )


@router.get(
    "/workspaces",
    response_model=ItemsResponse[WorkspaceResponse],
    responses=ERROR_RESPONSES,
    operation_id="list_workspaces",
)
def list_workspaces(
    user: CurrentUser,
    runtime: RuntimeDependency,
) -> ItemsResponse[WorkspaceResponse]:
    return ItemsResponse(
        items=[
            WorkspaceResponse(
                workspace_id=str(item.workspace.id),
                name=item.workspace.name,
                owner_user_id=str(item.workspace.owner_user_id),
                role=item.role.value,
            )
            for item in runtime.list_workspaces(user)
        ]
    )


def _token_response(grant) -> TokenResponse:
    return TokenResponse(
        access_token=grant.access_token,
        refresh_token=grant.refresh_token,
        expires_in=grant.access_expires_in,
        refresh_expires_in=grant.refresh_expires_in,
        user=UserResponse(user_id=str(grant.user.id), login=grant.user.login),
    )


__all__ = ["router"]
