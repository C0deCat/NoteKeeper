"""Voice-sample use-case group builder."""

from notekeeper.application import (
    AddVoiceSample,
    DeleteVoiceSample,
    ListVoiceSamples,
    SampleUseCases,
    UpdateVoiceSample,
)

from .guards import guard_campaign_mutation
from .wiring_context import UseCaseWiringContext


def build_sample_use_cases(context: UseCaseWiringContext) -> SampleUseCases:
    repositories = context.repositories
    services = context.services
    return SampleUseCases(
        add=guard_campaign_mutation(
            context,
            AddVoiceSample(
                repositories.campaign_repository,
                services.metadata_reader,
                services.source_metadata_reader,
                services.artifact_storage,
                services.id_generator,
            ),
        ),
        list=ListVoiceSamples(repositories.campaign_repository),
        update=guard_campaign_mutation(
            context,
            UpdateVoiceSample(
                repositories.campaign_repository,
                services.metadata_reader,
            ),
        ),
        delete=guard_campaign_mutation(
            context,
            DeleteVoiceSample(repositories.campaign_repository),
        ),
    )


__all__ = ["build_sample_use_cases"]
