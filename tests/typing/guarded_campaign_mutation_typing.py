"""Static Pyright contract for guarded campaign mutation inference."""

from dataclasses import dataclass
from typing import assert_type

from notekeeper.application import (
    UpdateCampaign,
    UpdateCampaignCommand,
    UpdateCampaignResult,
)
from notekeeper.application.use_cases.utils import (
    CampaignMutationPolicy,
    GuardedCampaignMutation,
)


@dataclass(frozen=True, slots=True)
class _Command:
    campaign_id: str


@dataclass(frozen=True, slots=True)
class _Result:
    campaign_id: str


class _UseCase:
    def execute(self, command: _Command) -> _Result:
        return _Result(campaign_id=command.campaign_id)


def check_guarded_campaign_mutation_inference(
    policy: CampaignMutationPolicy,
) -> None:
    guarded = GuardedCampaignMutation(_UseCase(), policy)

    assert_type(guarded, GuardedCampaignMutation[_Command, _Result])
    assert_type(guarded.execute(_Command(campaign_id="campaign-1")), _Result)


def check_concrete_use_case_inference(
    use_case: UpdateCampaign,
    policy: CampaignMutationPolicy,
) -> None:
    guarded = GuardedCampaignMutation(use_case, policy)

    assert_type(
        guarded,
        GuardedCampaignMutation[UpdateCampaignCommand, UpdateCampaignResult],
    )
    assert_type(
        guarded.execute(
            UpdateCampaignCommand(campaign_id="campaign-1", name="Updated"),
        ),
        UpdateCampaignResult,
    )
