"""Progress stage plans for processing use cases."""

from notekeeper.domain import ProcessingStage


def processing_stages(
    *,
    alignment_enabled: bool,
    diarization_enabled: bool,
) -> tuple[ProcessingStage, ...]:
    stages = [
        ProcessingStage.NORMALIZING_AUDIO,
        ProcessingStage.CONCATENATING_AUDIO,
        ProcessingStage.LOADING_TRANSCRIPTION_MODEL,
        ProcessingStage.TRANSCRIBING,
    ]
    if alignment_enabled:
        stages.extend(
            (
                ProcessingStage.LOADING_ALIGNMENT_MODEL,
                ProcessingStage.ALIGNING_TRANSCRIPT,
            ),
        )
    if diarization_enabled:
        stages.extend(
            (
                ProcessingStage.LOADING_DIARIZATION_MODEL,
                ProcessingStage.DIARIZING_SPEAKERS,
            ),
        )
    stages.extend(
        (
            ProcessingStage.MAPPING_SPEAKERS,
            ProcessingStage.GENERATING_RECAP,
        ),
    )
    return tuple(stages)


__all__ = ["processing_stages"]
