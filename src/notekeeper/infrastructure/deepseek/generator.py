"""DeepSeek recap-generation adapter."""

from __future__ import annotations

import time
from collections.abc import Callable

from notekeeper.application.ports import RecapGenerator
from notekeeper.application.results import RecapGenerationContext, TranscriptChunk
from notekeeper.domain import RecapChunk
from notekeeper.infrastructure.errors import (
    InfrastructureConfigurationError,
    InfrastructureError,
)

from .interfaces import (
    ChatMessage,
    DeepSeekChatClient,
    DeepSeekChatCompletion,
    DeepSeekRequestLogger,
)
from .noop_request_logger import NoOpDeepSeekRequestLogger
from .openai_client import OpenAIDeepSeekChatClient
from .utils import chunk_user_message, combined_user_message


class DeepSeekRecapGenerator(RecapGenerator):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com",
        model_name: str = "deepseek-v4-pro",
        temperature: float = 0.2,
        timeout_seconds: float = 120.0,
        retry_count: int = 2,
        retry_backoff_seconds: float = 1.0,
        client: DeepSeekChatClient | None = None,
        request_logger: DeepSeekRequestLogger | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._model_name = self._require_text(model_name, "model_name")
        self._temperature = self._require_non_negative_float(
            temperature,
            "temperature",
        )
        self._timeout_seconds = self._require_positive_float(
            timeout_seconds,
            "timeout_seconds",
        )
        self._retry_count = self._require_non_negative_int(
            retry_count,
            "retry_count",
        )
        self._retry_backoff_seconds = self._require_non_negative_float(
            retry_backoff_seconds,
            "retry_backoff_seconds",
        )
        self._client = client or OpenAIDeepSeekChatClient(
            api_key=api_key,
            base_url=base_url,
        )
        self._request_logger = request_logger or NoOpDeepSeekRequestLogger()
        self._sleep = sleep or time.sleep

    def generate_chunk(
        self,
        chunk: TranscriptChunk,
        *,
        guidance: str,
        context: RecapGenerationContext,
    ) -> str:
        return self._complete(
            (
                {
                    "role": "system",
                    "content": self._require_text(guidance, "chunk recap guidance"),
                },
                {"role": "user", "content": chunk_user_message(chunk)},
            ),
            context=context,
            operation="chunk_recap",
        )

    def combine_chunks(
        self,
        chunks: tuple[RecapChunk, ...],
        *,
        guidance: str,
        context: RecapGenerationContext,
    ) -> str:
        return self._complete(
            (
                {
                    "role": "system",
                    "content": self._require_text(
                        guidance,
                        "combined recap guidance",
                    ),
                },
                {"role": "user", "content": combined_user_message(chunks)},
            ),
            context=context,
            operation="combine_chunks",
        )

    def _complete(
        self,
        messages: tuple[ChatMessage, ...],
        *,
        context: RecapGenerationContext,
        operation: str,
    ) -> str:
        last_error: BaseException | None = None
        attempts = self._retry_count + 1

        for attempt_number in range(1, attempts + 1):
            completion: DeepSeekChatCompletion | None = None
            started_at = time.perf_counter()
            try:
                completion = self._client.complete(
                    model=self._model_name,
                    messages=messages,
                    temperature=self._temperature,
                    timeout_seconds=self._timeout_seconds,
                )
                text = self._require_text(completion.text, "DeepSeek response")
            except InfrastructureConfigurationError:
                raise
            except InfrastructureError as exc:
                self._log_attempt(
                    context=context,
                    operation=operation,
                    attempt_number=attempt_number,
                    max_attempts=attempts,
                    messages=messages,
                    completion=completion,
                    duration_seconds=time.perf_counter() - started_at,
                    status="failure",
                    error_message=str(exc),
                )
                last_error = exc
            except Exception as exc:
                self._log_attempt(
                    context=context,
                    operation=operation,
                    attempt_number=attempt_number,
                    max_attempts=attempts,
                    messages=messages,
                    completion=completion,
                    duration_seconds=time.perf_counter() - started_at,
                    status="failure",
                    error_message=str(exc),
                )
                last_error = exc
            else:
                self._log_attempt(
                    context=context,
                    operation=operation,
                    attempt_number=attempt_number,
                    max_attempts=attempts,
                    messages=messages,
                    completion=completion,
                    duration_seconds=time.perf_counter() - started_at,
                    status="success",
                    response_text=text,
                )
                return text

            if attempt_number < attempts:
                self._sleep(self._retry_backoff_seconds * (2 ** (attempt_number - 1)))

        assert last_error is not None
        raise InfrastructureError(
            f"DeepSeek request failed after {attempts} attempts: {last_error}",
        ) from last_error

    def _log_attempt(
        self,
        *,
        context: RecapGenerationContext,
        operation: str,
        attempt_number: int,
        max_attempts: int,
        messages: tuple[ChatMessage, ...],
        completion: DeepSeekChatCompletion | None,
        duration_seconds: float,
        status: str,
        error_message: str | None = None,
        response_text: str | None = None,
    ) -> None:
        self._request_logger.log_attempt(
            context=context,
            operation=operation,
            attempt_number=attempt_number,
            max_attempts=max_attempts,
            model=self._model_name,
            temperature=self._temperature,
            timeout_seconds=self._timeout_seconds,
            token_estimate=self._estimate_tokens(messages),
            duration_seconds=duration_seconds,
            status=status,
            request_id=completion.request_id if completion is not None else None,
            response_metadata=self._response_metadata(completion),
            error_message=error_message,
            messages=messages,
            response_text=response_text,
        )

    def _response_metadata(
        self,
        completion: DeepSeekChatCompletion | None,
    ) -> dict[str, object]:
        if completion is None:
            return {}

        metadata: dict[str, object] = {}
        if completion.usage is not None:
            metadata["usage"] = completion.usage
        if completion.finish_reason is not None:
            metadata["finish_reason"] = completion.finish_reason
        return metadata

    def _estimate_tokens(self, messages: tuple[ChatMessage, ...]) -> int:
        character_count = sum(len(message["content"]) for message in messages)
        return (character_count + 3) // 4

    def _require_text(self, value: str, field: str) -> str:
        text = value.strip()
        if not text:
            raise InfrastructureError(f"{field} must not be empty")
        return text

    def _require_positive_float(self, value: float, field: str) -> float:
        if value <= 0:
            raise InfrastructureError(f"{field} must be positive")
        return float(value)

    def _require_non_negative_float(self, value: float, field: str) -> float:
        if value < 0:
            raise InfrastructureError(f"{field} must be non-negative")
        return float(value)

    def _require_non_negative_int(self, value: int, field: str) -> int:
        if value < 0:
            raise InfrastructureError(f"{field} must be a non-negative integer")
        return value


__all__ = ["DeepSeekRecapGenerator"]
