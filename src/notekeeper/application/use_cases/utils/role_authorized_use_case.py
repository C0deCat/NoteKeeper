"""Workspace-role authorization at the use-case boundary."""

from typing import Generic, Protocol, TypeVar

from notekeeper.application import AccessContext
from notekeeper.application.errors import AuthorizationError
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
    ) -> None:
        self._use_case = use_case
        self._access = access

    def execute(self, command: CommandT) -> ResultT:
        if self._access.role is WorkspaceRole.VIEWER:
            raise AuthorizationError("viewer membership is read-only")
        return self._use_case.execute(command)


__all__ = ["ExecutableUseCase", "RoleAuthorizedUseCase"]
