"""
Rate Limiting Configuration (Step 6)

Provides centralized rate limiting for the GOB API using slowapi.
Protects against brute force attacks, DoS, and resource exhaustion.

LIMITS:
- Auth endpoints (login/signup): 10/minute per IP (strict - prevents brute force)
- Simulation endpoints (simulate, simulate-quarter): 30/minute per IP (moderate - normal gameplay ~10-20/min)
- Simulate-turn: 300/minute per IP (high - one request per possession; 300 allows normal play)
- General API: 100/minute per IP (lenient - normal browsing/loading)

USAGE:
    from BackEnd.utils.rate_limiter import limiter, get_remote_address

    @router.post("/login")
    @limiter.limit("10/minute")
    async def login(request: Request, ...):
        ...
"""

import os
from slowapi import Limiter
from slowapi.util import get_remote_address as _get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse


def get_remote_address(request: Request) -> str:
    """
    Get client IP address from request.
    Handles proxies (X-Forwarded-For) which Railway/Netlify use.
    """
    # Check for forwarded IP (behind proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can be comma-separated; first is the original client
        return forwarded.split(",")[0].strip()
    # Check for real IP header (some proxies use this)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    # Fall back to direct client IP
    return _get_remote_address(request)


# Rate limit strings (can be overridden via env vars for testing)
AUTH_RATE_LIMIT = os.getenv("RATE_LIMIT_AUTH", "10/minute")
SIM_RATE_LIMIT = os.getenv("RATE_LIMIT_SIM", "30/minute")
SIM_TURN_RATE_LIMIT = os.getenv("RATE_LIMIT_SIM_TURN", "300/minute")
GENERAL_RATE_LIMIT = os.getenv("RATE_LIMIT_GENERAL", "100/minute")

# Create the limiter instance
# Uses in-memory storage by default (sufficient for single-instance Railway deployment)
# For multi-instance, would need Redis backend
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[GENERAL_RATE_LIMIT],
    # Don't apply default limits automatically - we'll be explicit
    headers_enabled=True,  # Include X-RateLimit-* headers in responses
)


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
