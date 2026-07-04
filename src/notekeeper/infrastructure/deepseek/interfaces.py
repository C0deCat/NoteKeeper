"""Internal DeepSeek adapter protocols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypedDict

from notekeeper.application.results import RecapGenerationContext
from notekeeper.domain import ArtifactRef


class ChatMessage(TypedDict):
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class DeepSeekChatCompletion:
    text: str
    request_id: str | None = None
    usage: dict[str, Any] | None = None
    finish_reason: str | None = None

    def __post_init__(self) -> None:
        if self.usage is not None:
            object.__setattr__(self, "usage", dict(self.usage))


class DeepSeekChatClient(Protocol):
    def complete(
        self,
        *,
        model: str,
        messages: tuple[ChatMessage, ...],
        temperature: float,
        timeout_seconds: float,
    ) -> DeepSeekChatCompletion: ...


class DeepSeekRequestLogger(Protocol):
    def log_attempt(
        self,
        *,
        context: RecapGenerationContext,
        operation: str,
        attempt_number: int,
        max_attempts: int,
        model: str,
        temperature: float,
        timeout_seconds: float,
        token_estimate: int,
        duration_seconds: float,
        status: str,
        request_id: str | None = None,
        response_metadata: dict[str, Any] | None = None,
        error_message: str | None = None,
        messages: tuple[ChatMessage, ...] | None = None,
        response_text: str | None = None,
    ) -> ArtifactRef | None: ...


__all__ = [
    "ChatMessage",
    "DeepSeekChatClient",
    "DeepSeekChatCompletion",
    "DeepSeekRequestLogger",
]
