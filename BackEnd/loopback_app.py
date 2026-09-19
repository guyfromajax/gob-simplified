"""Wire the existing FastAPI app for local loopback. No new architecture."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from BackEnd.local_identity import get_local_user, get_local_user_optional
from BackEnd.loopback_env import is_loopback
from BackEnd.runtime_paths import bundle_path
from BackEnd.utils.auth import get_current_user, get_current_user_optional


class LoopbackProfileCookie(BaseHTTPMiddleware):
    """Tell the frontend this is the desktop profile without touching 80 HTML pages."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if is_loopback():
            response.set_cookie(
                "GOB_BUILD_PROFILE",
                "desktop",
                httponly=False,
                samesite="lax",
            )
        return response


def configure_loopback(app: FastAPI) -> FastAPI:
    """Inject the local principal and the desktop cookie. Auth Depends stay in place."""
    app.dependency_overrides[get_current_user] = get_local_user
    app.dependency_overrides[get_current_user_optional] = get_local_user_optional
    app.add_middleware(LoopbackProfileCookie)
    return app


def write_ready_file(host: str, port: int) -> Path:
    path = Path(os.environ.get("GOB_LOOPBACK_READY") or "/tmp/gob-loopback-ready.json")
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "host": host,
                "port": port,
                "persistence": os.environ.get("GOB_PERSISTENCE", "sqlite"),
                "pid": os.getpid(),
                "sqlite_path": os.environ.get("GOB_SQLITE_PATH"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def static_directory() -> Path:
    return bundle_path("FrontEnd", "static")
