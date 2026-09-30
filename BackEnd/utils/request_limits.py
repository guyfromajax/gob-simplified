"""Request body size cap (413) and input-free 422 validation errors.

Largest legitimate body measured on gob-staging (2026-09-30): the phase-a /
complete-week POST carrying one final game document, ~130 KB of JSON (stored franchise
game docs: median 80 KB, max 130 KB BSON). Playbook settings max 2.7 KB, strategy
settings 190 B; team-builder payloads are colour/name recipes, never images. The
default cap is 1 MiB (~8x that), overridable with GOB_MAX_REQUEST_BYTES.
See reports/security-batch-2-2026-09-30.md.
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping

from starlette.exceptions import HTTPException

DEFAULT_MAX_REQUEST_BYTES = 1024 * 1024
MAX_REQUEST_BYTES_ENV = "GOB_MAX_REQUEST_BYTES"


def max_request_bytes(environ: Mapping[str, str] | None = None) -> int:
    env = os.environ if environ is None else environ
    raw = str(env.get(MAX_REQUEST_BYTES_ENV) or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_REQUEST_BYTES
    return value if value > 0 else DEFAULT_MAX_REQUEST_BYTES


TOO_LARGE_DETAIL = "Request body too large"


class _BodyTooLarge(HTTPException):
    """Raised from receive() mid-stream. An HTTPException because FastAPI turns any
    other exception during body reading into a 400; this one passes through and the
    app's exception middleware renders it as 413 (CORS still applies outside)."""

    def __init__(self) -> None:
        super().__init__(status_code=413, detail=TOO_LARGE_DETAIL)


def _too_large_body() -> bytes:
    return json.dumps({"detail": TOO_LARGE_DETAIL}).encode()


class RequestSizeLimitMiddleware:
    """Pure ASGI. Rejects a declared Content-Length over the cap before reading the
    body, and stops a streamed (chunked / undeclared) body the moment it passes the
    cap. Either way the app sees nothing and the client gets 413."""

    def __init__(self, app, max_bytes: int | None = None):
        self.app = app
        self.max_bytes = max_bytes if max_bytes is not None else max_request_bytes()

    async def _send_413(self, send) -> None:
        body = _too_large_body()
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        })
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        limit = self.max_bytes
        for name, value in scope.get("headers") or ():
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    break
                if declared > limit:
                    await self._send_413(send)
                    return
                break

        received = 0
        response_started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body") or b"")
                if received > limit:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message):
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if response_started:
                raise
            await self._send_413(send)


def validation_error_payload(errors: list[dict[str, Any]]) -> dict[str, Any]:
    """FastAPI's 422 body without the submitted input: keep loc / msg / type only.

    The default handler echoes ``input`` (the whole offending value, e.g. a 57 MB
    junk body) and ``ctx`` / ``url``; nothing in FrontEnd reads those.
    """
    detail = []
    for err in errors:
        detail.append({
            "loc": list(err.get("loc") or ()),
            "msg": str(err.get("msg") or ""),
            "type": str(err.get("type") or ""),
        })
    return {"detail": detail}
