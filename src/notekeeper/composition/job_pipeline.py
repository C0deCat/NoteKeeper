"""Construction of the in-process processing pipeline."""

from notekeeper.application import RunProcessingJob

from .factory import InfrastructureBundle


def build_processing_pipeline(
    infrastructure: InfrastructureBundle,
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
        infrastructure.recap_generator,
        infrastructure.clock,
        infrastructure.id_generator,
    )


__all__ = ["build_processing_pipeline"]
