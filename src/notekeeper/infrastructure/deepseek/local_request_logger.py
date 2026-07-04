"""Local JSON artifact logging for DeepSeek request diagnostics."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from notekeeper.application.results import RecapGenerationContext
from notekeeper.domain import ArtifactRef
from notekeeper.infrastructure.filesystem.storage import LocalCampaignArtifactStorage
from notekeeper.infrastructure.filesystem.utils import safe_name

from .interfaces import ChatMessage, DeepSeekRequestLogger


class LocalDeepSeekRequestLogger(DeepSeekRequestLogger):
    def __init__(
        self,
        storage: LocalCampaignArtifactStorage,
        *,
        include_payloads: bool = False,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._storage = storage
        self._include_payloads = include_payloads
        self._now = now or (lambda: datetime.now(timezone.utc))

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
        payload = {
            "schema_version": 1,
            "created_at": self._now().isoformat(),
            "operation": operation,
            "status": status,
            "context": self._context_payload(context),
            "attempt": {
                "number": attempt_number,
                "max_attempts": max_attempts,
            },
            "request": {
                "model": model,
                "temperature": temperature,
                "timeout_seconds": timeout_seconds,
                "token_estimate": token_estimate,
                "prompt": self._prompt_metadata(messages),
            },
            "response": {
                "request_id": request_id,
                "duration_seconds": duration_seconds,
                "metadata": dict(response_metadata or {}),
            },
            "error_message": error_message,
        }
        if self._include_payloads:
            payload["payload"] = {
                "messages": list(messages or ()),
                "response_text": response_text,
            }

        return self._storage.save_campaign_text(
            campaign_id=context.campaign_id,
            folder="recaps",
            suggested_name=self._artifact_name(
                context=context,
                operation=operation,
                attempt_number=attempt_number,
            ),
            content=json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            media_type="application/json",
        )

    def _context_payload(self, context: RecapGenerationContext) -> dict[str, Any]:
        return {
            "campaign_id": str(context.campaign_id),
            "transcript_id": str(context.transcript_id),
            "recap_id": str(context.recap_id),
            "job_id": str(context.job_id) if context.job_id is not None else None,
            "chunk_index": context.chunk_index,
        }

    def _prompt_metadata(
        self,
        messages: tuple[ChatMessage, ...] | None,
    ) -> dict[str, Any]:
        messages = messages or ()
        return {
            "message_count": len(messages),
            "roles": [message["role"] for message in messages],
            "content_character_count": sum(
                len(message["content"]) for message in messages
            ),
        }

    def _artifact_name(
        self,
        *,
        context: RecapGenerationContext,
        operation: str,
        attempt_number: int,
    ) -> str:
        recap_name = safe_name(str(context.recap_id), "recap_id")
        operation_name = safe_name(operation, "operation")
        attempt_name = f"attempt-{attempt_number:03d}"
        if context.chunk_index is None:
            stem = f"{operation_name}-{attempt_name}.json"
        else:
            stem = (
                f"{operation_name}-chunk-{context.chunk_index:04d}-"
                f"{attempt_name}.json"
            )
        return f"llm-diagnostics/{recap_name}/{stem}"


__all__ = ["LocalDeepSeekRequestLogger"]
