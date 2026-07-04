from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from notekeeper.application.results import RecapGenerationContext, TranscriptChunk
from notekeeper.domain import (
    CampaignId,
    ProcessingJobId,
    RecapChunk,
    RecapId,
    TimeRange,
    TranscriptId,
)
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.deepseek import (
    DeepSeekRecapGenerator,
    LocalDeepSeekRequestLogger,
)
from notekeeper.infrastructure.deepseek.interfaces import DeepSeekChatCompletion
from notekeeper.infrastructure.filesystem import LocalCampaignArtifactStorage


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
    ) -> DeepSeekChatCompletion:
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
        if isinstance(response, DeepSeekChatCompletion):
            return response
        return DeepSeekChatCompletion(text=response)


def test_deepseek_generator_sends_chunk_prompt_and_returns_markdown() -> None:
    client = FakeDeepSeekClient("## Chunk Recap\nThe party enters the crypt.")
    generator = _generator(client)

    markdown = generator.generate_chunk(
        TranscriptChunk(
            text="[00:00:00 - 00:00:05] **Alice:** We enter the crypt.",
            time_range=TimeRange(0, 5),
            source_segment_indexes=(0,),
        ),
        context=_context(),
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
        context=_context(chunk_index=None),
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

    markdown = generator.generate_chunk(
        TranscriptChunk(text="hello"),
        context=_context(),
    )

    assert markdown == "## Chunk Recap\nRecovered."
    assert len(client.calls) == 2
    assert sleeps == [0.5]


def test_deepseek_generator_wraps_exhausted_retries() -> None:
    client = FakeDeepSeekClient(RuntimeError("temporary"), RuntimeError("still down"))
    generator = _generator(client, retry_count=1, sleep=lambda _: None)

    with pytest.raises(InfrastructureError, match="after 2 attempts"):
        generator.generate_chunk(TranscriptChunk(text="hello"), context=_context())


def test_deepseek_generator_rejects_empty_response() -> None:
    client = FakeDeepSeekClient("   ")
    generator = _generator(client, retry_count=0)

    with pytest.raises(InfrastructureError, match="empty"):
        generator.generate_chunk(TranscriptChunk(text="hello"), context=_context())


def test_deepseek_generator_requires_api_key_for_real_client() -> None:
    generator = DeepSeekRecapGenerator(
        chunk_recap_prompt="chunk prompt",
        combine_chunks_prompt="combine prompt",
        api_key=None,
        retry_count=0,
    )

    with pytest.raises(InfrastructureError, match="API key"):
        generator.generate_chunk(TranscriptChunk(text="hello"), context=_context())


def test_deepseek_request_logger_omits_full_payload_by_default(
    tmp_path: Path,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    logger = LocalDeepSeekRequestLogger(
        storage,
        now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    client = FakeDeepSeekClient(
        DeepSeekChatCompletion(
            text="## Chunk Recap\nSecret answer",
            request_id="request-1",
            usage={"prompt_tokens": 12, "completion_tokens": 5},
            finish_reason="stop",
        ),
    )
    generator = _generator(client, request_logger=logger)

    generator.generate_chunk(
        TranscriptChunk(text="secret transcript text"),
        context=_context(),
    )

    payload = _read_log(tmp_path, "chunk_recap-chunk-0000-attempt-001.json")
    raw_payload = json.dumps(payload)
    assert payload["status"] == "success"
    assert payload["context"]["job_id"] == "job-1"
    assert payload["context"]["chunk_index"] == 0
    assert payload["response"]["request_id"] == "request-1"
    assert payload["response"]["metadata"]["usage"]["prompt_tokens"] == 12
    assert payload["response"]["metadata"]["finish_reason"] == "stop"
    assert "payload" not in payload
    assert "secret transcript text" not in raw_payload
    assert "Secret answer" not in raw_payload


def test_deepseek_request_logger_can_include_full_payloads(
    tmp_path: Path,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    logger = LocalDeepSeekRequestLogger(storage, include_payloads=True)
    client = FakeDeepSeekClient("## Chunk Recap\nSecret answer")
    generator = _generator(client, request_logger=logger)

    generator.generate_chunk(
        TranscriptChunk(text="secret transcript text"),
        context=_context(),
    )

    payload = _read_log(tmp_path, "chunk_recap-chunk-0000-attempt-001.json")
    assert payload["payload"]["response_text"] == "## Chunk Recap\nSecret answer"
    assert "secret transcript text" in json.dumps(payload["payload"])


def test_deepseek_request_logger_records_retry_attempts(tmp_path: Path) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path)
    logger = LocalDeepSeekRequestLogger(storage)
    client = FakeDeepSeekClient(
        RuntimeError("temporary"),
        DeepSeekChatCompletion(
            text="## Chunk Recap\nRecovered.",
            request_id="request-2",
        ),
    )
    sleeps: list[float] = []
    generator = _generator(
        client,
        request_logger=logger,
        retry_count=1,
        sleep=sleeps.append,
    )

    markdown = generator.generate_chunk(
        TranscriptChunk(text="hello"),
        context=_context(),
    )

    assert markdown == "## Chunk Recap\nRecovered."
    assert sleeps == [0.5]
    first = _read_log(tmp_path, "chunk_recap-chunk-0000-attempt-001.json")
    second = _read_log(tmp_path, "chunk_recap-chunk-0000-attempt-002.json")
    assert first["status"] == "failure"
    assert first["attempt"] == {"max_attempts": 2, "number": 1}
    assert first["error_message"] == "temporary"
    assert second["status"] == "success"
    assert second["response"]["request_id"] == "request-2"


def _generator(
    client: FakeDeepSeekClient,
    *,
    retry_count: int = 0,
    request_logger=None,
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
        request_logger=request_logger,
        sleep=sleep,
    )


def _context(*, chunk_index: int | None = 0) -> RecapGenerationContext:
    return RecapGenerationContext(
        campaign_id=CampaignId("campaign-1"),
        transcript_id=TranscriptId("transcript-1"),
        recap_id=RecapId("recap-1"),
        job_id=ProcessingJobId("job-1"),
        chunk_index=chunk_index,
    )


def _read_log(tmp_path: Path, filename: str) -> dict:
    path = (
        tmp_path
        / "campaign-1"
        / "recaps"
        / "llm-diagnostics"
        / "recap-1"
        / filename
    )
    return json.loads(path.read_text(encoding="utf-8"))
