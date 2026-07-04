from __future__ import annotations

import pytest

from notekeeper.application.results import TranscriptChunk
from notekeeper.domain import RecapChunk, TimeRange
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.deepseek import DeepSeekRecapGenerator


class FakeDeepSeekClient:
    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def complete(
        self,
        *,
        model: str,
        messages: tuple[dict[str, str], ...],
        temperature: float,
        timeout_seconds: float,
    ) -> str:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "timeout_seconds": timeout_seconds,
            },
        )
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def test_deepseek_generator_sends_chunk_prompt_and_returns_markdown() -> None:
    client = FakeDeepSeekClient("## Chunk Recap\nThe party enters the crypt.")
    generator = _generator(client)

    markdown = generator.generate_chunk(
        TranscriptChunk(
            text="[00:00:00 - 00:00:05] **Alice:** We enter the crypt.",
            time_range=TimeRange(0, 5),
            source_segment_indexes=(0,),
        ),
    )

    assert markdown == "## Chunk Recap\nThe party enters the crypt."
    assert client.calls[0]["model"] == "test-model"
    assert client.calls[0]["temperature"] == 0.3
    assert client.calls[0]["timeout_seconds"] == 99.0
    assert client.calls[0]["messages"][0] == {
        "role": "system",
        "content": "chunk prompt",
    }
    assert "Transcript chunk:" in client.calls[0]["messages"][1]["content"]
    assert "source_segment_indexes: 0" in client.calls[0]["messages"][1]["content"]


def test_deepseek_generator_combines_partial_recaps_with_metadata() -> None:
    client = FakeDeepSeekClient("# Session Recap\nDone.")
    generator = _generator(client)

    markdown = generator.combine_chunks(
        (
            RecapChunk(
                markdown="## Part 1\nA clue appears.",
                time_range=TimeRange(0, 10),
                source_segment_indexes=(0, 1),
            ),
        ),
    )

    assert markdown == "# Session Recap\nDone."
    messages = client.calls[0]["messages"]
    assert messages[0] == {"role": "system", "content": "combine prompt"}
    assert "## Partial recap 1" in messages[1]["content"]
    assert "00:00:00 - 00:00:10" in messages[1]["content"]
    assert "source_segment_indexes: 0, 1" in messages[1]["content"]
    assert "## Part 1\nA clue appears." in messages[1]["content"]


def test_deepseek_generator_retries_after_temporary_failure() -> None:
    client = FakeDeepSeekClient(RuntimeError("temporary"), "## Chunk Recap\nRecovered.")
    sleeps: list[float] = []
    generator = _generator(client, retry_count=1, sleep=sleeps.append)

    markdown = generator.generate_chunk(TranscriptChunk(text="hello"))

    assert markdown == "## Chunk Recap\nRecovered."
    assert len(client.calls) == 2
    assert sleeps == [0.5]


def test_deepseek_generator_wraps_exhausted_retries() -> None:
    client = FakeDeepSeekClient(RuntimeError("temporary"), RuntimeError("still down"))
    generator = _generator(client, retry_count=1, sleep=lambda _: None)

    with pytest.raises(InfrastructureError, match="after 2 attempts"):
        generator.generate_chunk(TranscriptChunk(text="hello"))


def test_deepseek_generator_rejects_empty_response() -> None:
    client = FakeDeepSeekClient("   ")
    generator = _generator(client, retry_count=0)

    with pytest.raises(InfrastructureError, match="empty"):
        generator.generate_chunk(TranscriptChunk(text="hello"))


def test_deepseek_generator_requires_api_key_for_real_client() -> None:
    generator = DeepSeekRecapGenerator(
        chunk_recap_prompt="chunk prompt",
        combine_chunks_prompt="combine prompt",
        api_key=None,
        retry_count=0,
    )

    with pytest.raises(InfrastructureError, match="API key"):
        generator.generate_chunk(TranscriptChunk(text="hello"))


def _generator(
    client: FakeDeepSeekClient,
    *,
    retry_count: int = 0,
    sleep=None,
) -> DeepSeekRecapGenerator:
    return DeepSeekRecapGenerator(
        chunk_recap_prompt="chunk prompt",
        combine_chunks_prompt="combine prompt",
        model_name="test-model",
        temperature=0.3,
        timeout_seconds=99,
        retry_count=retry_count,
        retry_backoff_seconds=0.5,
        client=client,
        sleep=sleep,
    )
