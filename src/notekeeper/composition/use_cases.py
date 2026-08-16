"""Composition root for the grouped application use-case facade."""

from notekeeper.application import AccessContext, ApplicationUseCases
from notekeeper.application.ports import JobManager, ProgressTrackerFactory
from notekeeper.application.use_cases.utils import CampaignMutationPolicy

from .factory import LocalServices
from .repositories import WorkspaceRepositories
from .use_case_builders import (
    UseCaseWiringContext,
    build_campaign_use_cases,
    build_job_use_cases,
    build_media_use_cases,
    build_participant_use_cases,
    build_recap_use_cases,
    build_recording_use_cases,
    build_sample_use_cases,
    build_transcript_use_cases,
)


def wire_application_use_cases(
    services: LocalServices,
    repositories: WorkspaceRepositories,
    *,
    progress_tracker_factory: ProgressTrackerFactory,
    job_manager: JobManager,
    mutation_policy: CampaignMutationPolicy,
    access: AccessContext,
) -> ApplicationUseCases:
    context = UseCaseWiringContext(
        services,
        repositories,
        progress_tracker_factory,
        job_manager,
        mutation_policy,
        access,
    )
    return ApplicationUseCases(
        campaigns=build_campaign_use_cases(context),
        participants=build_participant_use_cases(context),
        samples=build_sample_use_cases(context),
        recordings=build_recording_use_cases(context),
        jobs=build_job_use_cases(context),
        transcripts=build_transcript_use_cases(context),
        recaps=build_recap_use_cases(context),
        media=build_media_use_cases(context),
    )


__all__ = ["wire_application_use_cases"]
