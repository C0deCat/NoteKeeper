"""Recap use-case group builder."""

from notekeeper.application import (
    ExportRecapMarkdown,
    GenerateRecap,
    PreviewRecapMarkdown,
    RecapUseCases,
)

from .guards import authorize_mutation
from .wiring_context import UseCaseWiringContext


def build_recap_use_cases(context: UseCaseWiringContext) -> RecapUseCases:
    repositories = context.repositories
    services = context.services
    return RecapUseCases(
        generate=authorize_mutation(
            context,
            GenerateRecap(
                repositories.job_repository,
                repositories.transcript_repository,
                repositories.recap_repository,
                services.tokenizer,
                services.recap_guidances,
                services.recap_generator,
                services.clock,
                services.id_generator,
                progress_tracker_factory=context.progress_tracker_factory,
            ),
        ),
        preview_markdown=PreviewRecapMarkdown(repositories.recap_repository),
        export_markdown=ExportRecapMarkdown(
            repositories.recap_repository,
            services.artifact_storage,
        ),
    )


__all__ = ["build_recap_use_cases"]
