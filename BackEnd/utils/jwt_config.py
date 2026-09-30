"""JWT signing-secret resolution. No DB imports: _bootstrap calls this at app boot.

The dev fallback secret is public (it is in this repo). It is accepted only in an
explicit local/dev/test environment that is not hosted. Anything else (staging,
production, an unknown name, or any Railway runtime) must set JWT_SECRET_KEY, or
the app refuses to start: a hosted app signing with a known secret lets anyone
forge a token for any user.
"""

from __future__ import annotations

import os
from typing import Mapping

DEV_JWT_FALLBACK = "dev-secret-key-change-in-production"
# Environment names allowed to run on the public dev secret (when not hosted).
DEV_JWT_ENVIRONMENTS = frozenset({"", "dev", "development", "local", "test"})


class JwtSecretNotConfigured(RuntimeError):
    """JWT_SECRET_KEY is missing (or the public dev value) in a hosted/non-dev env."""


def environment_name(environ: Mapping[str, str] = os.environ) -> str:
    return str(
        environ.get("ENVIRONMENT") or environ.get("ENV") or environ.get("RAILWAY_ENVIRONMENT") or ""
    ).strip().lower()


def is_hosted(environ: Mapping[str, str] = os.environ) -> bool:
    """Railway injects RAILWAY_* into every hosted runtime (same test as env_config)."""
    return any(str(key).startswith("RAILWAY_") for key in environ)


def resolve_jwt_secret(environ: Mapping[str, str] = os.environ) -> str:
    """The signing secret, or raise JwtSecretNotConfigured."""
    secret = str(environ.get("JWT_SECRET_KEY") or "")
    if secret and secret != DEV_JWT_FALLBACK:
        return secret
    env = environment_name(environ)
    if env in DEV_JWT_ENVIRONMENTS and not is_hosted(environ):
        return DEV_JWT_FALLBACK
    raise JwtSecretNotConfigured(
        "JWT_SECRET_KEY must be set to a private value "
        f"(environment={env or 'unset'!r}, hosted={is_hosted(environ)}). "
        "Set JWT_SECRET_KEY in the Railway service variables."
    )
