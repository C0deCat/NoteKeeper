"""ASGI request-body size enforcement for multipart uploads."""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .errors import RequestBodyTooLarge


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _is_upload_request(scope):
            await self._app(scope, receive, send)
            return
        content_length = _content_length(scope)
        if content_length is not None and content_length > self._max_bytes:
            await self._send_error(scope, send)
            return
        received = 0
        exceeded = False
        response_started = False
        replacement_sent = False

        async def limited_receive() -> Message:
            nonlocal exceeded, received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal replacement_sent, response_started
            if replacement_sent:
                return
            if message["type"] == "http.response.start":
                response_started = True
                if exceeded:
                    replacement_sent = True
                    await self._send_error(scope, send)
                    return
            await send(message)

        try:
            await self._app(scope, limited_receive, tracked_send)
        except RequestBodyTooLarge:
            if not response_started:
                await self._send_error(scope, send)

    async def _send_error(self, scope: Scope, send: Send) -> None:
        request_id = scope.get("state", {}).get("request_id", "req_unknown")
        body = json.dumps(
            {
                "error": {
                    "code": "payload_too_large",
                    "message": "Request payload is too large",
                    "request_id": request_id,
                    "details": {},
                }
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"x-request-id", request_id.encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def _is_upload_request(scope: Scope) -> bool:
    if scope.get("method") != "POST":
        return False
    path = str(scope.get("path", ""))
    return path.endswith("/recordings") or path.endswith("/voice-samples")


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", ()):
        if name.lower() == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


__all__ = ["RequestBodyLimitMiddleware"]
