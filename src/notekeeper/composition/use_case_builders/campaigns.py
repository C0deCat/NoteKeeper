"""Campaign use-case group builder."""

from notekeeper.application import (
    CampaignUseCases,
    CreateCampaign,
    DeleteCampaign,
    GetCampaign,
    GetRecapGuidances,
    ListCampaigns,
    SyncCampaignFolder,
    UpdateCampaign,
    UpdateRecapGuidances,
)

from .guards import authorize_mutation, guard_campaign_mutation
from .wiring_context import UseCaseWiringContext


def build_campaign_use_cases(context: UseCaseWiringContext) -> CampaignUseCases:
    repositories = context.repositories
    services = context.services
    return CampaignUseCases(
        create=authorize_mutation(
            context,
            CreateCampaign(
                repositories.campaign_repository,
                services.id_generator,
                services.recap_guidances,
                services.artifact_storage,
                context.access,
            ),
        ),
        get=GetCampaign(repositories.campaign_repository),
        list=ListCampaigns(repositories.campaign_repository),
        update=guard_campaign_mutation(
            context,
            UpdateCampaign(repositories.campaign_repository),
        ),
        delete=guard_campaign_mutation(
            context,
            DeleteCampaign(
                repositories.campaign_repository,
                services.artifact_storage,
            ),
        ),
        sync_folder=guard_campaign_mutation(
            context,
            SyncCampaignFolder(
                repositories.campaign_repository,
                repositories.job_repository,
                services.folder_scanner,
                services.metadata_reader,
                services.id_generator,
                audio_normalizer=services.audio_normalizer,
                artifact_storage=services.artifact_storage,
            ),
        ),
        get_recap_guidances=GetRecapGuidances(
            repositories.campaign_repository,
            services.recap_guidances,
        ),
        update_recap_guidances=guard_campaign_mutation(
            context,
            UpdateRecapGuidances(
                repositories.campaign_repository,
                services.recap_guidances,
            ),
        ),
    )


__all__ = ["build_campaign_use_cases"]
