"""FastAPI dependencies for identity and workspace-scoped sessions."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from notekeeper.application import AuthenticationRequiredError
from notekeeper.domain import AuthenticatedUser

from .contracts import ApiRuntime, ApiSession

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="NoteKeeperBearer",
    description="Opaque NoteKeeper access token.",
)


def get_runtime(request: Request) -> ApiRuntime:
    return cast(ApiRuntime, request.app.state.api_runtime)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise AuthenticationRequiredError("bearer access token is required")
    return runtime.resolve_user(credentials.credentials)


def get_personal_session(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> ApiSession:
    return runtime.personal_session(user)


def get_workspace_session(
    workspace_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> ApiSession:
    return runtime.workspace_session(user, workspace_id)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
PersonalSession = Annotated[ApiSession, Depends(get_personal_session)]
RuntimeDependency = Annotated[ApiRuntime, Depends(get_runtime)]
WorkspaceSession = Annotated[ApiSession, Depends(get_workspace_session)]

__all__ = [
    "CurrentUser",
    "PersonalSession",
    "RuntimeDependency",
    "WorkspaceSession",
    "bearer_scheme",
    "get_current_user",
    "get_personal_session",
    "get_runtime",
    "get_workspace_session",
]
