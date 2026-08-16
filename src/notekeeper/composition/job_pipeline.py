"""Construction of the in-process processing pipeline."""

from notekeeper.application import ExecuteQueuedProcessingJob
from notekeeper.application.ports import ProgressTrackerFactory
from notekeeper.application.use_cases.processing.progress import processing_stages

from .factory import LocalServices
from .repositories import RepositorySet


def build_processing_pipeline(
    services: LocalServices,
    repositories: RepositorySet,
    *,
    progress_tracker_factory: ProgressTrackerFactory | None = None,
) -> ExecuteQueuedProcessingJob:
    return ExecuteQueuedProcessingJob(
        repositories.campaign_repository,
        repositories.audio_track_repository,
        repositories.transcript_repository,
        repositories.recap_repository,
        repositories.job_repository,
        services.audio_processor,
        services.transcriber,
        services.speaker_identifier,
        repositories.speaker_mapping_repository,
        repositories.speaker_review_submission_repository,
        services.tokenizer,
        services.recap_guidances,
        services.recap_generator,
        services.clock,
        services.id_generator,
        progress_tracker_factory=progress_tracker_factory,
        progress_stages=processing_stages(
            alignment_enabled=(services.settings.whisperx_alignment_enabled),
            diarization_enabled=(services.settings.whisperx_diarization_enabled),
        ),
        transient_audio_cleaner=services.transient_audio_cleaner,
    )


__all__ = ["build_processing_pipeline"]
