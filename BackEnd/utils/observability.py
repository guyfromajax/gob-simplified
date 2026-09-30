"""Backend error reporting (Sentry): private, tagged, and quiet on healthy games.

Imported by BackEnd/api/api.py BEFORE the FastAPI app exists (the Sentry FastAPI
integration instruments app creation), so this module must stay import-light: no
store, no _bootstrap.

  environment  "production" / "staging" / "development" / "test" from the app's own
               ENVIRONMENT (set per Railway service), "desktop" on loopback. NOT
               RAILWAY_ENVIRONMENT(_NAME): staging and production are separate
               Railway projects whose environments are both named "production".
  release      the deployed git SHA (RAILWAY_GIT_COMMIT_SHA, ...), 12 chars.
  sampling     SENTRY_TRACES_SAMPLE_RATE, else 0.1 production / 0.02 elsewhere.
  desktop      OFF unless GOB_DESKTOP_SENTRY=1 (a player's machine never reports
               without an explicit opt-in).
  before_send  scrubs secrets/PII, truncates huge payloads, tags franchise/week/
               endpoint, and drops known healthy-game diagnostic log lines.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode

# ---------------------------------------------------------------------------
# environment / release / sampling / enablement
# ---------------------------------------------------------------------------

KNOWN_ENVIRONMENTS = {"production", "staging", "development", "test"}


def _is_loopback(environ: Mapping[str, str]) -> bool:
    return environ.get("GOB_LOOPBACK") == "1" or environ.get("GOB_BUILD_PROFILE") == "desktop"


def sentry_environment(environ: Mapping[str, str] = os.environ) -> str:
    if _is_loopback(environ):
        return "desktop"
    env = str(environ.get("ENVIRONMENT") or environ.get("ENV") or "").strip().lower()
    if env in {"prod"}:
        env = "production"
    if env in {"dev", "local"}:
        env = "development"
    if env in KNOWN_ENVIRONMENTS:
        return env
    return env or "development"


def sentry_release(environ: Mapping[str, str] = os.environ) -> str | None:
    sha = (
        environ.get("RAILWAY_GIT_COMMIT_SHA")
        or environ.get("GIT_COMMIT_SHA")
        or environ.get("SOURCE_VERSION")
        or environ.get("GOB_BUILD_ID")
        or _build_stamp()
        or ""
    ).strip()
    return sha[:12] or None


def _build_stamp() -> str:
    try:
        from BackEnd.runtime_paths import bundle_path

        path = bundle_path("BUILD_ID")
        if path.is_file():
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            return lines[0].strip() if lines else ""
    except Exception:
        pass
    return ""


def traces_sample_rate(environ: Mapping[str, str] = os.environ) -> float:
    raw = str(environ.get("SENTRY_TRACES_SAMPLE_RATE") or "").strip()
    if raw:
        try:
            return min(1.0, max(0.0, float(raw)))
        except ValueError:
            pass
    return 0.1 if sentry_environment(environ) == "production" else 0.02


def sentry_enabled(environ: Mapping[str, str] = os.environ) -> bool:
    if not str(environ.get("SENTRY_DSN") or "").strip():
        return False
    if _is_loopback(environ):
        return str(environ.get("GOB_DESKTOP_SENTRY") or "").strip().lower() in {"1", "true", "yes", "on"}
    return True


def init_sentry(environ: Mapping[str, str] = os.environ) -> bool:
    """Initialise the backend SDK if enabled. Returns True when initialised."""
    if not sentry_enabled(environ):
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=environ["SENTRY_DSN"],
        environment=sentry_environment(environ),
        release=sentry_release(environ),
        traces_sample_rate=traces_sample_rate(environ),
        send_default_pii=False,
        max_request_body_size="medium",
        before_send=before_send,
        before_send_transaction=before_send_transaction,
    )
    return True


# ---------------------------------------------------------------------------
# scrubbing
# ---------------------------------------------------------------------------

FILTERED = "[Filtered]"
SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}
# Exact (lower-cased) keys whose values are always secret or personal.
SENSITIVE_KEYS = {
    "password", "new_password", "old_password", "current_password", "password_hash",
    "token", "access_token", "refresh_token", "reset_token", "id_token", "jwt",
    "authorization", "cookie", "secret", "api_key", "apikey",
    "otp", "otp_code", "code", "access_code",
    "email", "user_email", "username_email",
    "stripe_signature", "card", "card_number", "cvc",
}
SENSITIVE_KEY_RE = re.compile(r"(password|passwd|secret|token|otp|email)", re.I)
# Big engine payloads: never ship them whole.
BULKY_KEYS = {
    "game_document", "final_game_document", "turns", "turn_log", "box_score", "game_state",
    "animations", "animation_steps", "players", "teams", "schedule", "results", "summary",
}
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
MAX_STRING = 2048
MAX_BULKY_BYTES = 1024
MAX_DEPTH = 12
AUTH_PATH_PREFIXES = ("/api/auth/",)
SENSITIVE_QUERY_KEYS = {"token", "email", "code", "otp", "otp_code", "access_code", "password"}


def scrub_string(value: str) -> str:
    value = JWT_RE.sub("[Filtered JWT]", value)
    value = BEARER_RE.sub("Bearer [Filtered]", value)
    value = EMAIL_RE.sub("[email]", value)
    if len(value) > MAX_STRING:
        value = value[:MAX_STRING] + f"...[truncated {len(value) - MAX_STRING} chars]"
    return value


def _size(value: Any) -> int:
    try:
        return len(json.dumps(value, default=str))
    except Exception:
        return len(str(value))


def scrub(value: Any, depth: int = 0) -> Any:
    """Recursively redact secrets/PII and shrink bulky payloads."""
    if depth > MAX_DEPTH:
        return "[truncated: too deep]"
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            key = str(k)
            low = key.lower()
            if low in SENSITIVE_KEYS or SENSITIVE_KEY_RE.search(low):
                out[k] = FILTERED
            elif low in BULKY_KEYS and _size(v) > MAX_BULKY_BYTES:
                out[k] = f"[truncated {low}: {_size(v)} bytes]"
            else:
                out[k] = scrub(v, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        items = [scrub(v, depth + 1) for v in value[:50]]
        if len(value) > 50:
            items.append(f"[truncated {len(value) - 50} more items]")
        return items
    if isinstance(value, str):
        return scrub_string(value)
    return value


def _scrub_query(qs: str) -> str:
    pairs = parse_qsl(qs, keep_blank_values=True)
    return urlencode([(k, FILTERED if k.lower() in SENSITIVE_QUERY_KEYS else scrub_string(v)) for k, v in pairs])


def _scrub_url(url: str) -> str:
    if "?" not in url:
        return scrub_string(url)
    base, _, qs = url.partition("?")
    return scrub_string(base) + "?" + _scrub_query(qs)


def scrub_request(request: dict) -> dict:
    req = dict(request)
    headers = req.get("headers")
    if isinstance(headers, dict):
        req["headers"] = {k: (FILTERED if str(k).lower() in SENSITIVE_HEADERS else scrub_string(str(v)))
                          for k, v in headers.items()}
    req.pop("cookies", None)
    env = req.get("env")
    if isinstance(env, dict):
        env.pop("REMOTE_ADDR", None)
    path = str(req.get("url") or "")
    if "data" in req:
        if any(p in path for p in AUTH_PATH_PREFIXES):
            req["data"] = "[Filtered: auth route body]"
        else:
            data = req["data"]
            if isinstance(data, str) and len(data) > MAX_BULKY_BYTES:
                req["data"] = f"[truncated body: {len(data)} chars]"
            else:
                req["data"] = scrub(data)
    if req.get("query_string"):
        req["query_string"] = _scrub_query(str(req["query_string"]))
    if req.get("url"):
        req["url"] = _scrub_url(str(req["url"]))
    return req


# ---------------------------------------------------------------------------
# noise: healthy-game diagnostics that are logged at ERROR but aren't errors
# ---------------------------------------------------------------------------

# Only lines shown (or documented in the audit) to fire on healthy games, and only
# when the event has NO exception attached — a real exception always flows.
NOISE_MESSAGE_PATTERNS = (
    re.compile(r"\[HCO ENTRY BUG\] current_bh_id is None"),  # also demoted at source
    re.compile(r"\[DIAG\] FALLING BACK TO DB"),
)


def _event_message(event: dict) -> str:
    logentry = event.get("logentry") or {}
    return str(logentry.get("formatted") or logentry.get("message") or event.get("message") or "")


def is_noise(event: dict) -> bool:
    if event.get("exception"):
        return False
    msg = _event_message(event)
    return any(p.search(msg) for p in NOISE_MESSAGE_PATTERNS)


# ---------------------------------------------------------------------------
# league tags (franchise_id / week / endpoint), no PII
# ---------------------------------------------------------------------------

def _league_tags(request: dict) -> dict:
    tags: dict[str, str] = {}
    found: dict[str, Any] = {}
    qs = request.get("query_string") or ""
    if isinstance(qs, str) and qs:
        found.update({k: v for k, v in parse_qsl(qs) if k in ("franchise_id", "week")})
    data = request.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = None
    if isinstance(data, dict):
        for k in ("franchise_id", "week"):
            if k in data and data[k] not in (None, ""):
                found.setdefault(k, data[k])
    if found.get("franchise_id") and re.fullmatch(r"[0-9a-fA-F]{24}", str(found["franchise_id"])):
        tags["franchise_id"] = str(found["franchise_id"])
    if found.get("week") is not None and re.fullmatch(r"\d{1,3}", str(found["week"])):
        tags["week"] = str(found["week"])
    url = str(request.get("url") or "")
    if url:
        path = "/" + url.split("://", 1)[-1].split("/", 1)[-1].split("?", 1)[0] if "://" in url else url.split("?", 1)[0]
        tags["endpoint"] = re.sub(r"/[0-9a-fA-F]{24}(?=/|$)", "/{id}", path)[:120]
    return tags


# ---------------------------------------------------------------------------
# hooks
# ---------------------------------------------------------------------------

def _scrub_event(event: dict) -> dict:
    request = event.get("request")
    if isinstance(request, dict):
        tags = _league_tags(request)  # before scrubbing (ids are not secret)
        event["request"] = scrub_request(request)
        if tags:
            event.setdefault("tags", {})
            if isinstance(event["tags"], dict):
                for k, v in tags.items():
                    event["tags"].setdefault(k, v)
    user = event.get("user")
    if isinstance(user, dict):
        event["user"] = {k: v for k, v in user.items() if k == "id"}
    for key in ("extra", "contexts"):
        if isinstance(event.get(key), dict):
            event[key] = scrub(event[key])
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        for k in ("message", "formatted"):
            if isinstance(logentry.get(k), str):
                logentry[k] = scrub_string(logentry[k])
        if logentry.get("params"):
            logentry["params"] = scrub(logentry["params"])
    if isinstance(event.get("message"), str):
        event["message"] = scrub_string(event["message"])
    for exc in ((event.get("exception") or {}).get("values") or []):
        if isinstance(exc, dict) and isinstance(exc.get("value"), str):
            exc["value"] = scrub_string(exc["value"])
        for frame in ((exc.get("stacktrace") or {}).get("frames") or []) if isinstance(exc, dict) else []:
            if not isinstance(frame, dict):
                continue
            if isinstance(frame.get("vars"), dict):
                frame["vars"] = scrub(frame["vars"])
            # Source context lines ride along with every frame; scrub them like any text.
            if isinstance(frame.get("context_line"), str):
                frame["context_line"] = scrub_string(frame["context_line"])
            for key in ("pre_context", "post_context"):
                if isinstance(frame.get(key), list):
                    frame[key] = [scrub_string(x) if isinstance(x, str) else x for x in frame[key]]
    for thread in ((event.get("threads") or {}).get("values") or []):
        for frame in ((thread.get("stacktrace") or {}).get("frames") or []) if isinstance(thread, dict) else []:
            if isinstance(frame, dict) and isinstance(frame.get("vars"), dict):
                frame["vars"] = scrub(frame["vars"])
    crumbs = event.get("breadcrumbs")
    values = crumbs.get("values") if isinstance(crumbs, dict) else crumbs
    if isinstance(values, list):
        for crumb in values:
            if isinstance(crumb, dict):
                if isinstance(crumb.get("message"), str):
                    crumb["message"] = scrub_string(crumb["message"])
                if isinstance(crumb.get("data"), dict):
                    crumb["data"] = scrub(crumb["data"])
    return event


def before_send(event: dict, hint: dict | None = None) -> dict | None:
    try:
        if is_noise(event):
            return None
        return _scrub_event(event)
    except Exception:
        # Never let the scrubber leak an unscrubbed event: drop it instead.
        return None


def before_send_transaction(event: dict, hint: dict | None = None) -> dict | None:
    try:
        return _scrub_event(event)
    except Exception:
        return None
