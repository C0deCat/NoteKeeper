"""Construction of the in-process processing pipeline."""

from notekeeper.application import RunProcessingJob
from notekeeper.application.ports import ProgressTrackerFactory
from notekeeper.application.use_cases.processing.progress import processing_stages

from .factory import InfrastructureBundle


def build_processing_pipeline(
    infrastructure: InfrastructureBundle,
    *,
    progress_tracker_factory: ProgressTrackerFactory | None = None,
) -> RunProcessingJob:
    return RunProcessingJob(
        infrastructure.campaign_repository,
        infrastructure.audio_track_repository,
        infrastructure.transcript_repository,
        infrastructure.recap_repository,
        infrastructure.job_repository,
        infrastructure.audio_processor,
        infrastructure.transcriber,
        infrastructure.speaker_identifier,
        infrastructure.speaker_mapping_repository,
        infrastructure.tokenizer,
        infrastructure.recap_guidances,
        infrastructure.recap_generator,
        infrastructure.clock,
        infrastructure.id_generator,
        progress_tracker_factory=progress_tracker_factory,
        progress_stages=processing_stages(
            alignment_enabled=(
                infrastructure.settings.whisperx_alignment_enabled
            ),
            diarization_enabled=(
                infrastructure.settings.whisperx_diarization_enabled
            ),
        ),
        transient_audio_cleaner=infrastructure.transient_audio_cleaner,
    )


__all__ = ["build_processing_pipeline"]
