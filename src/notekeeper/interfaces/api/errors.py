"""HTTP-adapter error values."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    details: object = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


class RequestBodyTooLarge(Exception):
    """Raised when the ASGI request stream exceeds the configured limit."""


__all__ = ["ApiError", "RequestBodyTooLarge"]
