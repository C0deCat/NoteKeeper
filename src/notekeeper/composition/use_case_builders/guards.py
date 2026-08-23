"""Application-boundary policy wiring helpers."""

from notekeeper.application.use_cases.utils import (
    GuardedCampaignMutation,
    RoleAuthorizedUseCase,
)

from .wiring_context import UseCaseWiringContext


def guard_campaign_mutation(context: UseCaseWiringContext, use_case):
    return GuardedCampaignMutation(
        use_case,
        context.mutation_policy,
        campaign_repository=context.repositories.campaign_repository,
        access=context.access,
        workspace_repository=context.services.workspace_repository,
    )


def authorize_mutation(context: UseCaseWiringContext, use_case):
    return RoleAuthorizedUseCase(
        use_case,
        context.access,
        context.services.workspace_repository,
    )


__all__ = ["authorize_mutation", "guard_campaign_mutation"]
