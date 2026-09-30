"""Observability: Sentry privacy/tagging/noise, and /health/ready."""

from __future__ import annotations

import json
import logging
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from slowapi import Limiter

from BackEnd.api import _bootstrap
from BackEnd.api.api import app
from BackEnd.utils import observability as obs
from BackEnd.utils import rate_limiter

client = TestClient(app)

JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2YWJjZGVmMDEyMzQ1Njc4OTBhYmNkZWYifQ.c2lnbmF0dXJlLWxvb2tpbmctc3R1ZmY"
FID = "6abcdef0123456789abcdef0"


# --- environment / release / sampling / enablement ---------------------------------


@pytest.mark.parametrize("environ,expected", [
    ({"ENVIRONMENT": "production", "RAILWAY_ENVIRONMENT_NAME": "production"}, "production"),
    # staging is its own Railway PROJECT whose environment is also named "production":
    ({"ENVIRONMENT": "staging", "RAILWAY_ENVIRONMENT_NAME": "production"}, "staging"),
    ({"ENVIRONMENT": "development"}, "development"),
    ({"ENVIRONMENT": "prod"}, "production"),
    ({}, "development"),
    ({"GOB_LOOPBACK": "1", "ENVIRONMENT": "development"}, "desktop"),
    ({"GOB_BUILD_PROFILE": "desktop"}, "desktop"),
])
def test_environment(environ, expected):
    assert obs.sentry_environment(environ) == expected


def test_release_is_the_deployed_sha():
    assert obs.sentry_release({"RAILWAY_GIT_COMMIT_SHA": "0123456789abcdef0123"}) == "0123456789ab"
    assert obs.sentry_release({"GOB_BUILD_ID": "desk1234"}) == "desk1234"


@pytest.mark.parametrize("environ,expected", [
    ({"ENVIRONMENT": "production"}, 0.1),
    ({"ENVIRONMENT": "staging"}, 0.02),
    ({"ENVIRONMENT": "production", "SENTRY_TRACES_SAMPLE_RATE": "0.05"}, 0.05),
    ({"ENVIRONMENT": "staging", "SENTRY_TRACES_SAMPLE_RATE": "2"}, 1.0),
    ({"ENVIRONMENT": "production", "SENTRY_TRACES_SAMPLE_RATE": "junk"}, 0.1),
])
def test_traces_sample_rate(environ, expected):
    assert obs.traces_sample_rate(environ) == expected


def test_desktop_is_off_unless_explicitly_opted_in():
    dsn = {"SENTRY_DSN": "https://k@example.invalid/1"}
    assert obs.sentry_enabled({**dsn, "ENVIRONMENT": "production"}) is True
    assert obs.sentry_enabled({**dsn, "GOB_LOOPBACK": "1"}) is False
    assert obs.sentry_enabled({**dsn, "GOB_LOOPBACK": "1", "GOB_DESKTOP_SENTRY": "1"}) is True
    assert obs.sentry_enabled({"ENVIRONMENT": "production"}) is False  # no DSN


# --- scrubber ---------------------------------------------------------------------------


def _event(url, data=None, query="", **extra):
    ev = {
        "request": {
            "url": url, "method": "POST", "query_string": query,
            "headers": {"Authorization": f"Bearer {JWT}", "Cookie": "session=abc", "User-Agent": "UA",
                        "Content-Type": "application/json"},
            "cookies": {"session": "abc"}, "env": {"REMOTE_ADDR": "203.0.113.9"},
            "data": data if data is not None else {},
        },
        "user": {"id": "6abcdef0123456789abcdef1", "email": "coach@example.com", "ip_address": "203.0.113.9"},
    }
    ev.update(extra)
    return ev


def _blob(ev) -> str:
    return json.dumps(ev, default=str)


def test_headers_cookies_ip_and_user_email_are_removed():
    out = obs.before_send(_event("https://api.example.com/franchise/team-data"))
    h = out["request"]["headers"]
    assert h["Authorization"] == obs.FILTERED and h["Cookie"] == obs.FILTERED
    assert h["User-Agent"] == "UA"
    assert "cookies" not in out["request"] and "REMOTE_ADDR" not in out["request"]["env"]
    assert out["user"] == {"id": "6abcdef0123456789abcdef1"}
    blob = _blob(out)
    assert JWT not in blob and "coach@example.com" not in blob and "203.0.113.9" not in blob


def test_auth_route_bodies_are_dropped_entirely():
    body = {"email": "coach@example.com", "password": "Hunter22!", "otp_code": "ABCDEF1234"}
    out = obs.before_send(_event("https://api.example.com/api/auth/signup", data=body))
    assert out["request"]["data"] == "[Filtered: auth route body]"
    reset = obs.before_send(_event("https://api.example.com/api/auth/reset-password",
                                   data={"token": "raw-reset-token-xyz", "new_password": "N3wPassword"}))
    assert "raw-reset-token-xyz" not in _blob(reset) and "N3wPassword" not in _blob(reset)


def test_secret_keys_tokens_and_emails_are_redacted_anywhere():
    data = {"franchise_id": FID, "week": 7, "nested": {"access_code": "T123456789", "reset_token": "abc",
            "note": f"user coach@example.com sent {JWT}"}}
    ev = _event("https://api.example.com/franchise/recruiting-orders", data=data,
                query="franchise_id=%s&token=secret-reset&email=coach%%40example.com" % FID,
                extra={"payload": {"password": "p4ss", "api_key": "sk_live_123"}},
                exception={"values": [{"type": "ValueError",
                                       "value": f"bad login for coach@example.com with {JWT}"}]},
                breadcrumbs={"values": [{"message": f"Authorization: Bearer {JWT}",
                                         "data": {"otp": "999999"}}]})
    out = obs.before_send(ev)
    blob = _blob(out)
    for secret in ("coach@example.com", JWT, "T123456789", "secret-reset", "p4ss", "sk_live_123", "999999"):
        assert secret not in blob, secret
    assert out["request"]["data"]["franchise_id"] == FID  # ids are kept
    assert "token=%5BFiltered%5D" in out["request"]["query_string"]


def test_huge_payloads_are_truncated_not_shipped():
    game_doc = {"turns": [{"i": i, "steps": ["x" * 200] * 10} for i in range(400)], "box_score": {"p": "y" * 50000}}
    ev = _event("https://api.example.com/franchise/complete-week/phase-a",
                data={"franchise_id": FID, "week": 3, "game_document": game_doc})
    raw = len(_blob(ev))
    out = obs.before_send(ev)
    assert str(out["request"]["data"]["game_document"]).startswith("[truncated game_document:")
    assert len(_blob(out)) < raw / 50
    long_str = obs.before_send(_event("https://api.example.com/x", data={"blob": "z" * 100000}))
    assert len(long_str["request"]["data"]["blob"]) < 2200


def test_league_tags_franchise_week_endpoint():
    out = obs.before_send(_event(f"https://api.example.com/franchise/complete-week/phase-b",
                                 data={"franchise_id": FID, "week": 12}))
    assert out["tags"]["franchise_id"] == FID
    assert out["tags"]["week"] == "12"
    assert out["tags"]["endpoint"] == "/franchise/complete-week/phase-b"
    q = obs.before_send(_event(f"https://api.example.com/api/game/{FID}/resume-state",
                               query=f"franchise_id={FID}&week=4"))
    assert q["tags"]["endpoint"] == "/api/game/{id}/resume-state" and q["tags"]["week"] == "4"


def test_transactions_are_scrubbed_too():
    out = obs.before_send_transaction(_event("https://api.example.com/api/auth/login",
                                             data={"email": "a@b.co", "password": "x"}))
    assert "a@b.co" not in _blob(out) and out["request"]["headers"]["Authorization"] == obs.FILTERED


def test_scrubber_failure_drops_the_event_rather_than_leaking(monkeypatch):
    monkeypatch.setattr(obs, "_scrub_event", lambda e: (_ for _ in ()).throw(RuntimeError("boom")))
    assert obs.before_send(_event("https://api.example.com/x")) is None


# --- noise filter ------------------------------------------------------------------------


def test_known_healthy_game_lines_are_dropped_but_real_errors_kept():
    hco = {"logentry": {"message": "❌❌❌ [HCO ENTRY BUG] current_bh_id is None — prior turn failed to stamp"}}
    diag = {"logentry": {"formatted": "🔴🔴🔴 [DIAG] FALLING BACK TO DB - GameManager missing playbook_settings!"}}
    assert obs.before_send(hco) is None and obs.before_send(diag) is None
    real = {"logentry": {"message": "[FINALIZE_GAME] boom"},
            "exception": {"values": [{"type": "KeyError", "value": "'teams'"}]}}
    assert obs.before_send(real) is not None
    also_real = dict(hco, exception={"values": [{"type": "RuntimeError", "value": "x"}]})
    assert obs.before_send(also_real) is not None  # an exception always flows


def test_real_sdk_end_to_end_tags_and_filters():
    """A real sentry_sdk client (in-memory transport): what would actually reach Sentry."""
    import sentry_sdk
    from sentry_sdk.transport import Transport

    events = []

    class Capture(Transport):
        def capture_envelope(self, envelope):
            ev = envelope.get_event()
            if ev is not None:
                events.append(ev)

    environ = {"SENTRY_DSN": "https://pub@example.invalid/1", "ENVIRONMENT": "staging",
               "RAILWAY_ENVIRONMENT_NAME": "production", "RAILWAY_GIT_COMMIT_SHA": "feedfacecafe1234"}
    sentry_sdk.init(dsn=environ["SENTRY_DSN"], environment=obs.sentry_environment(environ),
                    release=obs.sentry_release(environ), send_default_pii=False,
                    before_send=obs.before_send, transport=Capture)
    try:
        log = logging.getLogger("obs-e2e")
        log.error("❌❌❌ [HCO ENTRY BUG] current_bh_id is None — prior turn failed to stamp a final ball handler.")
        log.error("🔴🔴🔴 [DIAG] FALLING BACK TO DB - GameManager missing playbook_settings!")
        try:
            raise ValueError(f"simulated 5xx for coach@example.com {JWT}")
        except ValueError:
            sentry_sdk.capture_exception()
        sentry_sdk.flush()
    finally:
        sentry_sdk.init()  # no DSN: disabled client for the rest of the suite
    assert len(events) == 1, [e.get("logentry") for e in events]
    ev = events[0]
    assert ev["environment"] == "staging" and ev["release"] == "feedfacecafe"
    assert "coach@example.com" not in _blob(ev) and JWT not in _blob(ev)


# --- /health/ready ------------------------------------------------------------------------


@pytest.fixture
def readiness():
    saved = dict(_bootstrap._readiness)
    yield _bootstrap
    _bootstrap._readiness.clear()
    _bootstrap._readiness.update(saved)


def test_ready_503_before_startup(readiness):
    readiness._readiness.update({"startup_complete": False, "ping": lambda: None})
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.json() == {"status": "not_ready"}


def test_ready_200_when_db_answers(readiness):
    readiness.mark_startup_complete(lambda: None)
    r = client.get("/health/ready")
    assert r.status_code == 200 and r.json() == {"status": "ready"}


def test_ready_503_when_ping_fails_without_leaking_details(readiness):
    def boom():
        raise RuntimeError("mongodb+srv://user:pw@cluster/ timeout")
    readiness.mark_startup_complete(boom)
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.json() == {"status": "not_ready"}
    assert "mongodb" not in r.text


def test_ready_503_when_ping_hangs(readiness, monkeypatch):
    monkeypatch.setattr(readiness, "READY_PING_TIMEOUT_S", 0.2)
    readiness.mark_startup_complete(lambda: time.sleep(2))
    t0 = time.time()
    r = client.get("/health/ready")
    assert r.status_code == 503 and time.time() - t0 < 1.5


def test_ready_and_health_are_exempt_from_the_default_rate_limit(readiness, monkeypatch):
    readiness.mark_startup_complete(lambda: None)
    low = Limiter(key_func=rate_limiter.get_remote_address, default_limits=["2/minute"])
    monkeypatch.setattr(rate_limiter.limiter, "_default_limits", low._default_limits)
    headers = {"X-Real-IP": f"198.19.{uuid.uuid4().int % 250}.7"}
    assert all(client.get("/health/ready", headers=headers).status_code == 200 for _ in range(6))
    assert all(client.get("/health", headers=headers).status_code == 200 for _ in range(6))
    assert client.get("/app-config", headers=headers).status_code == 200
    assert client.get("/app-config", headers=headers).status_code == 200
    assert client.get("/app-config", headers=headers).status_code == 429  # default limit is live


def test_app_config_exposes_environment_and_release_for_the_browser_sdk():
    body = client.get("/app-config", headers={"X-Real-IP": f"198.19.{uuid.uuid4().int % 250}.8"}).json()
    assert body["sentryEnvironment"] in obs.KNOWN_ENVIRONMENTS | {"desktop"}
    assert "release" in body
