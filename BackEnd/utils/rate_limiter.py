"""
Rate Limiting Configuration (Step 6)

Provides centralized rate limiting for the GOB API using slowapi.
Protects against brute force attacks, DoS, and resource exhaustion.

LIMITS:
- Auth endpoints (login/signup): 10/minute per IP (strict - prevents brute force)
- Simulation endpoints (simulate, simulate-quarter): 30/minute per IP (moderate - normal gameplay ~10-20/min)
- Simulate-turn: 300/minute per IP (high - one request per possession; 300 allows normal play)
- General API default: 300/minute per IP, applied by SlowAPIASGIMiddleware to every
  route without its own limit (/health exempt; OPTIONS preflights never match a route)
- Heavy franchise routes: per user (bearer token sub, else IP) via user_rate_limit()

CLIENT KEY: X-Real-IP (set by Railway's edge), else the RIGHTMOST X-Forwarded-For
entry (the one the nearest proxy appended), else the socket peer. Never the leftmost
X-Forwarded-For entry: the client writes that one, so keying on it let any client
dodge every limit by sending a fake header.

USAGE:
    from BackEnd.utils.rate_limiter import limiter, get_remote_address

    @router.post("/login")
    @limiter.limit("10/minute")
    async def login(request: Request, ...):
        ...
"""

import math
import os
import time
from slowapi import Limiter
from slowapi.util import get_remote_address as _get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from limits import parse as _parse_limit

from BackEnd.loopback_env import is_loopback


def get_remote_address(request: Request) -> str:
    """
    Client IP for rate limiting (see CLIENT KEY above). Never the leftmost
    X-Forwarded-For entry, which the client controls.
    """
    real_ip = (request.headers.get("X-Real-IP") or "").strip()
    if real_ip:
        return real_ip
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    # Fall back to direct client IP
    return _get_remote_address(request)


def get_user_or_ip(request: Request) -> str:
    """Per-user key: the bearer token's user id when it verifies, else the client IP."""
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        try:
            from BackEnd.utils.auth import decode_token

            payload = decode_token(auth.split(" ", 1)[1].strip())
            if payload and payload.get("sub"):
                return f"user:{payload['sub']}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"


# Rate limit strings (can be overridden via env vars for testing)
AUTH_RATE_LIMIT = os.getenv("RATE_LIMIT_AUTH", "10/minute")
SIM_RATE_LIMIT = os.getenv("RATE_LIMIT_SIM", "30/minute")
SIM_TURN_RATE_LIMIT = os.getenv("RATE_LIMIT_SIM_TURN", "300/minute")
GENERAL_RATE_LIMIT = os.getenv("RATE_LIMIT_GENERAL", "300/minute")
# Heavy franchise routes (per user). Each call is minutes of CPU sim or a season
# rollover; the UI issues them single-flight, once per game/week/season.
WEEK_ADVANCE_RATE_LIMIT = os.getenv("RATE_LIMIT_WEEK_ADVANCE", "10/minute")
CPU_SIMS_RATE_LIMIT = os.getenv("RATE_LIMIT_CPU_SIMS", "6/minute")
FINISH_SEASON_RATE_LIMIT = os.getenv("RATE_LIMIT_FINISH_SEASON", "3/minute")

# Create the limiter instance
# Uses in-memory storage by default (sufficient for single-instance Railway deployment)
# For multi-instance, would need Redis backend
limiter = Limiter(
    key_func=get_remote_address,
    # Applied to every route without its own @limiter.limit by the middleware that
    # api.py installs (install_default_rate_limit). Explicit limits still win.
    default_limits=[GENERAL_RATE_LIMIT],
    headers_enabled=True,  # Include X-RateLimit-* headers in responses
)


def install_default_rate_limit(app, *, exempt=()) -> None:
    """Apply GENERAL_RATE_LIMIT to every route that has no explicit limit.

    `exempt` are endpoint functions (liveness checks) that must never be limited.
    Uses the pure-ASGI middleware (the BaseHTTPMiddleware variant breaks streaming
    responses and contextvars). Installed INNERMOST (appended, not add_middleware,
    which would wrap it outside CORSMiddleware) so a 429 still carries CORS headers.
    OPTIONS preflights never match a route handler, so they are never limited.
    """
    from slowapi.middleware import SlowAPIASGIMiddleware
    from starlette.middleware import Middleware

    for fn in exempt:
        limiter.exempt(fn)
    app.user_middleware.append(Middleware(SlowAPIASGIMiddleware))


def user_rate_limit(limit: str, scope: str):
    """FastAPI dependency: `limit` per user (token sub) else per IP, for `scope`.

    A dependency rather than @limiter.limit, so the route function's signature is
    unchanged (callers and tests invoke several of these routes directly).
    """
    item = _parse_limit(limit)

    def _check(request: Request) -> None:
        # Desktop (loopback) omits rate limiting entirely, same as api.py.
        if not limiter.enabled or is_loopback():
            return
        key = get_user_or_ip(request)
        strategy = limiter.limiter
        if not strategy.hit(item, scope, key):
            reset_at = strategy.get_window_stats(item, scope, key).reset_time
            retry_after = max(1, math.ceil(reset_at - time.time()))
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Please try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return _check


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors.
    Returns a clear 429 response with retry information.
    """
    # Get the limit that was exceeded from the exception
    retry_after = getattr(exc, "retry_after", 60)
    
    response = JSONResponse(
        status_code=429,
        content={
            "error": "Too many requests",
            "detail": f"Rate limit exceeded. Please try again in {retry_after} seconds.",
            "retry_after": retry_after,
        },
    )
    # Add standard rate limit headers
    response.headers["Retry-After"] = str(retry_after)
    response.headers["X-RateLimit-Limit"] = str(exc.detail) if hasattr(exc, "detail") else "unknown"
    return response
