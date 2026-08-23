"""Recording use-case group builder."""

from notekeeper.application import (
    DeleteAudioTrack,
    ListAudioTracks,
    RecordingUseCases,
    RegisterAudioTrack,
    SubmitRecordingForProcessing,
    UpdateAudioTrack,
)

from .guards import guard_campaign_mutation
from .wiring_context import UseCaseWiringContext


def build_recording_use_cases(context: UseCaseWiringContext) -> RecordingUseCases:
    repositories = context.repositories
    services = context.services
    return RecordingUseCases(
        register=guard_campaign_mutation(
            context,
            RegisterAudioTrack(
                repositories.campaign_repository,
                services.metadata_reader,
                services.id_generator,
                audio_normalizer=services.audio_normalizer,
                artifact_storage=services.artifact_storage,
            ),
        ),
        list=ListAudioTracks(repositories.campaign_repository),
        update=guard_campaign_mutation(
            context,
            UpdateAudioTrack(
                repositories.campaign_repository,
                services.metadata_reader,
                audio_normalizer=services.audio_normalizer,
                artifact_storage=services.artifact_storage,
            ),
        ),
        delete=guard_campaign_mutation(
            context,
            DeleteAudioTrack(
                repositories.campaign_repository,
                repositories.job_repository,
            ),
        ),
        submit_for_processing=guard_campaign_mutation(
            context,
            SubmitRecordingForProcessing(
                repositories.campaign_repository,
                repositories.audio_track_repository,
                repositories.job_repository,
                services.metadata_reader,
                services.source_metadata_reader,
                services.artifact_storage,
                services.clock,
                services.id_generator,
                audio_normalizer=services.audio_normalizer,
                settings_service=context.settings_service,
            ),
        ),
    )


__all__ = ["build_recording_use_cases"]
