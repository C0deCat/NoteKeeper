"""Composition root for the grouped application use-case facade."""

from notekeeper.application import (
    AccessContext,
    ApplicationUseCases,
    Authenticator,
    SettingsService,
)
from notekeeper.domain import SettingsCatalog
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
    authenticator: Authenticator,
) -> ApplicationUseCases:
    settings_service = SettingsService(
        access,
        services.workspace_repository,
        services.workspace_settings_repository,
        services.user_preferences_repository,
        repositories.campaign_repository,
        services.recap_guidances,
        authenticator,
        SettingsCatalog(
            whisperx_models=services.settings.whisperx_available_model_names,
            whisperx_languages=services.settings.whisperx_available_languages,
            deepseek_models=services.settings.deepseek_available_model_names,
        ),
        default_whisperx_model_name=services.settings.whisperx_model_name,
        default_whisperx_language=services.settings.whisperx_language,
        default_deepseek_model_name=services.settings.deepseek_model_name,
        default_deepseek_temperature=services.settings.deepseek_temperature,
    )
    context = UseCaseWiringContext(
        services,
        repositories,
        progress_tracker_factory,
        job_manager,
        mutation_policy,
        access,
        settings_service,
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
        settings=settings_service,
    )


__all__ = ["wire_application_use_cases"]
