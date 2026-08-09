"""Tests for processing progress plans and recap work fractions."""

from notekeeper.application import TranscriptChunk
from notekeeper.application.use_cases._recaps import generate_recap_for_transcript
from notekeeper.application.use_cases.processing.progress import processing_stages
from notekeeper.domain import (
    AudioTrackId,
    CampaignId,
    ProcessingStage,
    Transcript,
    TranscriptId,
)


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


def test_recap_progress_includes_each_chunk_and_combination() -> None:
    fractions: list[float] = []
    saved = []

    class Ids:
        def recap_id(self) -> str:
            return "recap-1"

    class FourChunkTokenizer:
        def split_transcript(self, transcript, *, target_token_count):
            return tuple(TranscriptChunk(text=f"chunk {index}") for index in range(4))

    class Guidances:
        def get_chunk_recap_guidances(self, campaign_id) -> str:
            return "chunk guidance"

        def get_combined_recap_guidances(self, campaign_id) -> str:
            return "combined guidance"

    class Generator:
        def generate_chunk(self, chunk, *, guidance, context) -> str:
            return chunk.text

        def combine_chunks(self, chunks, *, guidance, context) -> str:
            return "combined"

    class Repository:
        def save(self, recap) -> None:
            saved.append(recap)

    generate_recap_for_transcript(
        Transcript(
            id=TranscriptId("transcript-1"),
            campaign_id=CampaignId("campaign-1"),
            audio_track_id=AudioTrackId("audio-track-1"),
        ),
        id_generator=Ids(),
        tokenizer=FourChunkTokenizer(),
        recap_guidances=Guidances(),
        recap_generator=Generator(),
        recap_repository=Repository(),
        progress_callback=fractions.append,
    )

    assert fractions == [0.2, 0.4, 0.6, 0.8, 1.0]
    assert len(saved) == 1
