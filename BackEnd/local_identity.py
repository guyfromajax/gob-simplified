"""Synthetic desktop principal. Injected via FastAPI dependency override."""

from __future__ import annotations

LOCAL_USER_ID = "local-desktop-user"

LOCAL_PRINCIPAL: dict[str, str] = {
    "user_id": LOCAL_USER_ID,
    "email": "local@desktop",
    "role": "user",
    "username": "Coach",
}


async def get_local_user() -> dict[str, str]:
    return dict(LOCAL_PRINCIPAL)


async def get_local_user_optional() -> dict[str, str]:
    return dict(LOCAL_PRINCIPAL)
