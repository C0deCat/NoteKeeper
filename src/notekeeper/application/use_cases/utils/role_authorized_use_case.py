"""Workspace-role authorization at the use-case boundary."""

from typing import Generic, Protocol, TypeVar

from notekeeper.application import AccessContext
from notekeeper.application.errors import AuthorizationError
from notekeeper.application.ports import WorkspaceRepository
from notekeeper.domain import WorkspaceRole

CommandT = TypeVar("CommandT")
ResultT = TypeVar("ResultT")


class ExecutableUseCase(Protocol[CommandT, ResultT]):
    def execute(self, command: CommandT) -> ResultT: ...


class RoleAuthorizedUseCase(Generic[CommandT, ResultT]):
    def __init__(
        self,
        use_case: ExecutableUseCase[CommandT, ResultT],
        access: AccessContext,
        workspace_repository: WorkspaceRepository | None = None,
    ) -> None:
        self._use_case = use_case
        self._access = access
        self._workspace_repository = workspace_repository

    def execute(self, command: CommandT) -> ResultT:
        role = self._access.role
        if self._workspace_repository is not None:
            membership = self._workspace_repository.membership(
                self._access.workspace_id,
                self._access.actor_user_id,
            )
            if membership is None:
                raise AuthorizationError("workspace access has been revoked")
            role = membership.role
        if role is WorkspaceRole.VIEWER:
            raise AuthorizationError("viewer membership is read-only")
        return self._use_case.execute(command)


__all__ = ["ExecutableUseCase", "RoleAuthorizedUseCase"]
