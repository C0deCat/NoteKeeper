"""Authentication and identity schemas."""

from pydantic import Field

from .common import ApiSchema


class CredentialsRequest(ApiSchema):
    login: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshTokenRequest(ApiSchema):
    refresh_token: str = Field(min_length=1)


class UserResponse(ApiSchema):
    user_id: str
    login: str


class TokenResponse(ApiSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    user: UserResponse


class MeResponse(UserResponse):
    default_workspace_id: str | None = None


class WorkspaceResponse(ApiSchema):
    workspace_id: str
    name: str
    owner_user_id: str
    role: str


__all__ = [
    "CredentialsRequest",
    "MeResponse",
    "RefreshTokenRequest",
    "TokenResponse",
    "UserResponse",
    "WorkspaceResponse",
]
