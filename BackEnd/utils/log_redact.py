"""
Redact sensitive fields from data before logging.

Use before logging request bodies, headers, exceptions, or DB documents
to avoid exposing passwords, tokens, emails, or other PII.

Usage:
    from BackEnd.utils.log_redact import redact_sensitive

    safe = redact_sensitive({"email": "u@x.com", "password": "secret"})
    logger.info("Request: %s", safe)  # {"email": "[REDACTED]", "password": "[REDACTED]"}
"""

from typing import Any


# Keys (case-insensitive) that should be redacted
REDACT_KEYS = frozenset({
    "authorization", "cookie", "password", "password_hash", "hashed_password",
    "token", "access_token", "refresh_token", "api_key", "secret",
    "email", "email_address",
})

# Keys that may contain sensitive sub-values (e.g. Authorization: Bearer xxx)
HEADER_REDACT = frozenset({"authorization", "cookie"})


def _redact_value(key: str, value: Any) -> Any:
    """Return redacted value for known sensitive keys."""
    key_lower = key.lower() if isinstance(key, str) else ""
    if key_lower in REDACT_KEYS:
        return "[REDACTED]"
    if key_lower == "authorization" and isinstance(value, str):
        if value.lower().startswith("bearer "):
            return "Bearer [REDACTED]"
    return value


def redact_sensitive(data: Any, depth: int = 0, max_depth: int = 10) -> Any:
    """
    Recursively redact sensitive fields from a structure.

    Args:
        data: dict, list, or other value
        depth: current recursion depth (internal)
        max_depth: max recursion depth to avoid cycles

    Returns:
        Copy of data with sensitive values replaced by "[REDACTED]"
    """
    if depth > max_depth:
        return "[MAX_DEPTH]"
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            out[k] = redact_sensitive(_redact_value(k, v), depth + 1, max_depth)
        return out
    if isinstance(data, list):
        return [redact_sensitive(x, depth + 1, max_depth) for x in data]
    return data


def redact_headers(headers: dict) -> dict:
    """Redact Authorization and Cookie headers from a headers dict."""
    out = {}
    for k, v in headers.items():
        key_lower = k.lower() if isinstance(k, str) else ""
        if key_lower in HEADER_REDACT:
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out
