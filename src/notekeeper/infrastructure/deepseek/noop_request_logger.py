"""No-op DeepSeek request diagnostics logger."""

from __future__ import annotations

from typing import Any

from notekeeper.application.results import RecapGenerationContext
from notekeeper.domain import ArtifactRef

from .interfaces import ChatMessage, DeepSeekRequestLogger


class NoOpDeepSeekRequestLogger(DeepSeekRequestLogger):
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
    ) -> ArtifactRef | None:
        return None


__all__ = ["NoOpDeepSeekRequestLogger"]
