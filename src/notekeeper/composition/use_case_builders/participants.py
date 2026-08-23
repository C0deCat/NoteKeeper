"""Participant use-case group builder."""

from notekeeper.application import (
    AddParticipantToCampaign,
    DeleteParticipant,
    ListParticipants,
    ParticipantUseCases,
    UpdateParticipant,
)

from .guards import guard_campaign_mutation
from .wiring_context import UseCaseWiringContext


def build_participant_use_cases(context: UseCaseWiringContext) -> ParticipantUseCases:
    repositories = context.repositories
    return ParticipantUseCases(
        add=guard_campaign_mutation(
            context,
            AddParticipantToCampaign(
                repositories.campaign_repository,
                context.services.id_generator,
            ),
        ),
        list=ListParticipants(repositories.campaign_repository),
        update=guard_campaign_mutation(
            context,
            UpdateParticipant(repositories.campaign_repository),
        ),
        delete=guard_campaign_mutation(
            context,
            DeleteParticipant(repositories.campaign_repository),
        ),
    )


__all__ = ["build_participant_use_cases"]
