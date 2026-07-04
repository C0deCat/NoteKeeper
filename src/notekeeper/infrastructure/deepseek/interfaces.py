"""Internal DeepSeek adapter protocols."""

from __future__ import annotations

from typing import Protocol, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class DeepSeekChatClient(Protocol):
    def complete(
        self,
        *,
        model: str,
        messages: tuple[ChatMessage, ...],
        temperature: float,
        timeout_seconds: float,
    ) -> str: ...


__all__ = ["ChatMessage", "DeepSeekChatClient"]
