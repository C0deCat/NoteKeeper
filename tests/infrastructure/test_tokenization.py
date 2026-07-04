from __future__ import annotations

import pytest

from notekeeper.application.results import TranscriptChunk
from notekeeper.domain import (
    AudioTrackId,
    CampaignId,
    SpeakerLabel,
    TimeRange,
    Transcript,
    TranscriptId,
    TranscriptSegment,
)
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.tokenization import TiktokenTranscriptTokenizer


def test_tokenizer_splits_transcript_on_segment_boundaries() -> None:
    tokenizer = TiktokenTranscriptTokenizer(max_token_count=200)
    transcript = _transcript(
        _segment(0, 0, 1, "Alice", "We enter the crypt."),
        _segment(1, 1, 2, "Bob", "The door closes behind us."),
        _segment(2, 2, 3, "Alice", "I light a torch."),
    )

    chunks = tokenizer.split_transcript(transcript, target_token_count=22)

    assert len(chunks) == 3
    assert chunks[0].text == (
        "[00:00:00 - 00:00:01] **Alice:** We enter the crypt."
    )
    assert chunks[1].source_segment_indexes == (1,)
    assert chunks[2].source_segment_indexes == (2,)


def test_tokenizer_preserves_chunk_time_ranges_and_segments() -> None:
    tokenizer = TiktokenTranscriptTokenizer(max_token_count=200)
    first = _segment(3, 10.2, 12.8, "Alice", "First beat.")
    second = _segment(4, 12.8, 20.1, "Bob", "Second beat.")

    chunks = tokenizer.split_transcript(
        _transcript(first, second),
        target_token_count=200,
    )

    assert len(chunks) == 1
    assert chunks[0].segments == (first, second)
    assert chunks[0].source_segment_indexes == (3, 4)
    assert chunks[0].time_range == TimeRange(10.2, 20.1)


def test_tokenizer_splits_very_long_segment_by_max_token_count() -> None:
    tokenizer = TiktokenTranscriptTokenizer(max_token_count=40)
    segment = _segment(0, 0, 5, "Alice", " ".join(["omen"] * 160))

    chunks = tokenizer.split_transcript(
        _transcript(segment),
        target_token_count=200,
    )

    assert len(chunks) > 1
    assert all(chunk.segments == (segment,) for chunk in chunks)
    assert all(chunk.source_segment_indexes == (0,) for chunk in chunks)
    assert all(chunk.time_range == TimeRange(0, 5) for chunk in chunks)
    assert all(
        chunk.text.startswith("[00:00:00 - 00:00:05] **Alice:**")
        for chunk in chunks
    )


def test_tokenizer_returns_single_empty_chunk_for_empty_transcript() -> None:
    tokenizer = TiktokenTranscriptTokenizer()

    chunks = tokenizer.split_transcript(_transcript(), target_token_count=10)

    assert chunks == (TranscriptChunk(text=""),)


def test_tokenizer_rejects_invalid_limits_and_encoding() -> None:
    with pytest.raises(InfrastructureError, match="max_token_count"):
        TiktokenTranscriptTokenizer(max_token_count=0)

    tokenizer = TiktokenTranscriptTokenizer()
    with pytest.raises(InfrastructureError, match="target_token_count"):
        tokenizer.split_transcript(_transcript(), target_token_count=0)

    with pytest.raises(InfrastructureError, match="could not load tokenizer encoding"):
        TiktokenTranscriptTokenizer(encoding_name="missing-encoding")


def _transcript(*segments: TranscriptSegment) -> Transcript:
    return Transcript(
        id=TranscriptId("transcript-1"),
        campaign_id=CampaignId("campaign-1"),
        audio_track_id=AudioTrackId("audio-track-1"),
        segments=segments,
    )


def _segment(
    index: int,
    start: float,
    end: float,
    speaker: str,
    text: str,
) -> TranscriptSegment:
    return TranscriptSegment(
        index=index,
        time_range=TimeRange(start, end),
        speaker_label=SpeakerLabel.named(speaker),
        text=text,
    )
