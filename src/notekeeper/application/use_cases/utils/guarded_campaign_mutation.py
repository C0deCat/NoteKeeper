"""Typed whole-use-case campaign mutation guard."""

from typing import Generic, Protocol, TypeVar

from notekeeper.domain import CampaignId

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
    ) -> None:
        self._use_case = use_case
        self._policy = policy

    def execute(self, command: CommandT) -> ResultT:
        campaign_id = CampaignId(command.campaign_id)
        with self._policy.mutation(campaign_id):
            return self._use_case.execute(command)


__all__ = [
    "CampaignMutationCommand",
    "CampaignMutationUseCase",
    "GuardedCampaignMutation",
]
