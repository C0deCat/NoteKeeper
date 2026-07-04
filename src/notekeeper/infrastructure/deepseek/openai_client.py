"""OpenAI-compatible DeepSeek chat client."""

from __future__ import annotations

from typing import Any

from notekeeper.infrastructure.errors import InfrastructureError

from .interfaces import ChatMessage, DeepSeekChatClient, DeepSeekChatCompletion


class OpenAIDeepSeekChatClient(DeepSeekChatClient):
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = "https://api.deepseek.com",
    ) -> None:
        self._api_key = self._optional_text(api_key)
        self._base_url = self._require_text(base_url, "base_url")
        self._client: Any | None = None

    def complete(
        self,
        *,
        model: str,
        messages: tuple[ChatMessage, ...],
        temperature: float,
        timeout_seconds: float,
    ) -> DeepSeekChatCompletion:
        if self._api_key is None:
            raise InfrastructureError("DeepSeek API key is required")

        client = self._client_or_create()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=list(messages),
                temperature=temperature,
                timeout=timeout_seconds,
            )
        except Exception as exc:
            raise InfrastructureError("DeepSeek API request failed") from exc

        return self._completion_from_response(response)

    def _client_or_create(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise InfrastructureError("openai SDK is not installed") from exc

            try:
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                )
            except Exception as exc:
                raise InfrastructureError(
                    "could not create DeepSeek API client",
                ) from exc
        return self._client

    def _completion_from_response(self, response) -> DeepSeekChatCompletion:
        try:
            choice = response.choices[0]
            content = choice.message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise InfrastructureError("DeepSeek API returned malformed response") from exc

        if not isinstance(content, str) or not content.strip():
            raise InfrastructureError("DeepSeek API returned empty response")
        return DeepSeekChatCompletion(
            text=content.strip(),
            request_id=self._optional_response_text(
                getattr(response, "id", None) or getattr(response, "_request_id", None),
            ),
            usage=self._usage_payload(getattr(response, "usage", None)),
            finish_reason=self._optional_response_text(
                getattr(choice, "finish_reason", None),
            ),
        )

    def _usage_payload(self, usage: Any) -> dict[str, Any] | None:
        if usage is None:
            return None

        model_dump = getattr(usage, "model_dump", None)
        if callable(model_dump):
            payload = model_dump()
            return payload if isinstance(payload, dict) else None

        to_dict = getattr(usage, "dict", None)
        if callable(to_dict):
            payload = to_dict()
            return payload if isinstance(payload, dict) else None

        if isinstance(usage, dict):
            return dict(usage)

        values = getattr(usage, "__dict__", None)
        return dict(values) if isinstance(values, dict) else None

    def _optional_response_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    def _require_text(self, value: str, field: str) -> str:
        text = value.strip()
        if not text:
            raise InfrastructureError(f"{field} must not be empty")
        return text


__all__ = ["OpenAIDeepSeekChatClient"]
