"""Tests for processing progress plans and recap work fractions."""

from notekeeper.application.use_cases.processing.progress import processing_stages
from notekeeper.domain import ProcessingStage


def test_processing_stage_plan_excludes_disabled_optional_work() -> None:
    stages = processing_stages(
        alignment_enabled=False,
        diarization_enabled=False,
    )

    assert stages == (
        ProcessingStage.NORMALIZING_AUDIO,
        ProcessingStage.CONCATENATING_AUDIO,
        ProcessingStage.LOADING_TRANSCRIPTION_MODEL,
        ProcessingStage.TRANSCRIBING,
        ProcessingStage.MAPPING_SPEAKERS,
        ProcessingStage.GENERATING_RECAP,
    )


def test_full_processing_stage_plan_has_ten_ordered_stages() -> None:
    stages = processing_stages(
        alignment_enabled=True,
        diarization_enabled=True,
    )

    assert len(stages) == 10
    assert stages[0] is ProcessingStage.NORMALIZING_AUDIO
    assert stages[-1] is ProcessingStage.GENERATING_RECAP
