"""Processing-job use-case group builder."""

from notekeeper.application import (
    CancelProcessingJob,
    ClearFailedJobsForCampaign,
    CreateProcessingJobForAudioTrack,
    DeleteProcessingJob,
    GetJobStatus,
    JobUseCases,
    ListJobsForCampaign,
    QueueProcessingJob,
    RestartProcessingJob,
    ReviewSpeakerMappings,
)
from notekeeper.application.use_cases.utils import GuardedJobQueue

from .guards import authorize_mutation
from .wiring_context import UseCaseWiringContext


def build_job_use_cases(context: UseCaseWiringContext) -> JobUseCases:
    repositories = context.repositories
    services = context.services
    queue = QueueProcessingJob(
        repositories.job_repository,
        context.job_manager,
        services.clock,
        context.settings_service,
    )
    restart = RestartProcessingJob(
        repositories.campaign_repository,
        repositories.audio_track_repository,
        repositories.job_repository,
        services.clock,
        services.id_generator,
        context.settings_service,
    )
    return JobUseCases(
        create=authorize_mutation(
            context,
            CreateProcessingJobForAudioTrack(
                repositories.campaign_repository,
                repositories.audio_track_repository,
                repositories.job_repository,
                services.clock,
                services.id_generator,
                context.settings_service,
            ),
        ),
        queue=GuardedJobQueue(
            queue,
            context.mutation_policy,
            repositories.campaign_repository,
            repositories.job_repository,
            context.access,
            context.services.workspace_repository,
        ),
        restart_failed=authorize_mutation(context, restart),
        restart=authorize_mutation(context, restart),
        clear_failed=authorize_mutation(
            context,
            ClearFailedJobsForCampaign(
                repositories.campaign_repository,
                repositories.job_repository,
                services.job_cleaner,
            ),
        ),
        delete=authorize_mutation(
            context,
            DeleteProcessingJob(
                repositories.job_repository,
                services.job_cleaner,
            ),
        ),
        cancel=authorize_mutation(
            context,
            CancelProcessingJob(
                repositories.job_repository,
                services.clock,
                context.job_manager,
                repositories.speaker_review_submission_repository,
            ),
        ),
        list_for_campaign=ListJobsForCampaign(
            repositories.campaign_repository,
            repositories.job_repository,
        ),
        get_status=GetJobStatus(repositories.job_repository),
        review_speaker_mappings=authorize_mutation(
            context,
            ReviewSpeakerMappings(
                repositories.campaign_repository,
                repositories.transcript_repository,
                repositories.job_repository,
                repositories.speaker_review_submission_repository,
                context.job_manager,
                services.clock,
            ),
        ),
    )


__all__ = ["build_job_use_cases"]
