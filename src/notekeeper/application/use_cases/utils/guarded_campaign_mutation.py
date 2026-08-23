"""Typed whole-use-case campaign mutation guard."""

from typing import Generic, Protocol, TypeVar

from notekeeper.application import AccessContext
from notekeeper.application.errors import AuthorizationError, NotFoundError
from notekeeper.application.ports import CampaignRepository, WorkspaceRepository
from notekeeper.domain import CampaignId, WorkspaceRole

from .campaign_mutation_policy import CampaignMutationPolicy


class CampaignMutationCommand(Protocol):
    @property
    def campaign_id(self) -> str: ...


CommandT_contra = TypeVar(
    "CommandT_contra",
    bound=CampaignMutationCommand,
    contravariant=True,
)
ResultT_co = TypeVar("ResultT_co", covariant=True)


class CampaignMutationUseCase(Protocol[CommandT_contra, ResultT_co]):
    def execute(self, command: CommandT_contra) -> ResultT_co: ...


CommandT = TypeVar("CommandT", bound=CampaignMutationCommand)
ResultT = TypeVar("ResultT")


class GuardedCampaignMutation(Generic[CommandT, ResultT]):
    def __init__(
        self,
        use_case: CampaignMutationUseCase[CommandT, ResultT],
        policy: CampaignMutationPolicy,
        *,
        campaign_repository: CampaignRepository | None = None,
        access: AccessContext | None = None,
        workspace_repository: WorkspaceRepository | None = None,
    ) -> None:
        self._use_case = use_case
        self._policy = policy
        self._campaign_repository = campaign_repository
        self._access = access
        self._workspace_repository = workspace_repository

    def execute(self, command: CommandT) -> ResultT:
        campaign_id = CampaignId(command.campaign_id)
        if self._access is not None:
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
        if (
            self._campaign_repository is not None
            and self._campaign_repository.get(campaign_id) is None
        ):
            raise NotFoundError(f"campaign {campaign_id} was not found")
        with self._policy.mutation(campaign_id):
            return self._use_case.execute(command)


__all__ = [
    "CampaignMutationCommand",
    "CampaignMutationUseCase",
    "GuardedCampaignMutation",
]
