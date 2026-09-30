"""Auth hardening: real auth (no dependency override) end to end.

JWT secret gate, token_version revocation, DB-backed admin role, rate-limit key and
default limit, hashed reset tokens, signup enumeration, bcrypt 72-byte handling,
auth unique indexes and the read-only dupes script.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from slowapi import Limiter
from starlette.requests import Request

from BackEnd.api import auth_routes
from BackEnd.api.api import app
from BackEnd.db import alpha_otps_collection, password_reset_tokens_collection, users_collection
from BackEnd.persistence import indexes
from BackEnd.utils import auth, rate_limiter
from BackEnd.utils.auth import get_current_user, get_current_user_optional
from BackEnd.utils.jwt_config import DEV_JWT_FALLBACK, JwtSecretNotConfigured, resolve_jwt_secret
from scripts.generate_alpha_otps import build_alpha_otp_document
from scripts.ops.check_auth_dupes import blocks_index, find_auth_dupes

client = TestClient(app)
PASSWORD = "Password1"


@pytest.fixture(autouse=True)
def _real_auth(monkeypatch):
    """No auth override: exercise the real get_current_user."""
    saved = {dep: app.dependency_overrides.pop(dep) for dep in (get_current_user, get_current_user_optional)
             if dep in app.dependency_overrides}
    auth.invalidate_user_auth_cache()
    monkeypatch.setenv("IS_ALPHA", "false")
    monkeypatch.setattr(auth_routes, "send_password_reset_email", lambda *a, **k: True)
    yield
    auth.invalidate_user_auth_cache()
    app.dependency_overrides.update(saved)


def _ip() -> dict:
    """A unique client IP per call site, so the 10/minute auth limit never collides."""
    n = uuid.uuid4().int
    return {"X-Real-IP": f"198.51.{n % 250}.{(n >> 8) % 250 + 1}"}


def _email(prefix="coach") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def _signup(email=None, password=PASSWORD):
    email = email or _email()
    res = client.post("/api/auth/signup", json={"email": email, "password": password}, headers=_ip())
    assert res.status_code == 200, res.text
    return email, res.json()["token"], res.json()["user"]["user_id"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **_ip()}


def _me(token: str) -> int:
    return client.get("/api/auth/me", headers=_bearer(token)).status_code


# --- 1. JWT secret -------------------------------------------------------------


@pytest.mark.parametrize("environ", [
    {"ENVIRONMENT": "test"},
    {"ENVIRONMENT": "development"},
    {"ENVIRONMENT": "dev"},
    {"ENVIRONMENT": "local"},
    {},
])
def test_dev_fallback_allowed_only_for_local_dev_and_test(environ):
    assert resolve_jwt_secret(environ) == DEV_JWT_FALLBACK


@pytest.mark.parametrize("environ", [
    {"ENVIRONMENT": "staging"},
    {"ENVIRONMENT": "production"},
    {"ENVIRONMENT": "prod"},
    {"RAILWAY_ENVIRONMENT": "staging"},
    {"ENVIRONMENT": "test", "RAILWAY_PROJECT_ID": "x"},       # hosted wins over a dev name
    {"ENVIRONMENT": "development", "RAILWAY_ENVIRONMENT": "production"},
    {"ENVIRONMENT": "staging", "JWT_SECRET_KEY": DEV_JWT_FALLBACK},  # the public value is not a secret
])
def test_hosted_or_non_dev_env_refuses_without_private_secret(environ):
    with pytest.raises(JwtSecretNotConfigured):
        resolve_jwt_secret(environ)


def test_private_secret_accepted_anywhere():
    assert resolve_jwt_secret({"ENVIRONMENT": "production", "RAILWAY_ENVIRONMENT": "production",
                               "JWT_SECRET_KEY": "s3cret-value"}) == "s3cret-value"


def test_token_forged_with_dev_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "a-private-staging-secret-" + uuid.uuid4().hex)
    _, token, user_id = _signup()
    assert _me(token) == 200
    forged = jwt.encode(
        {"sub": user_id, "role": "admin", "tv": 0,
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        DEV_JWT_FALLBACK, algorithm="HS256",
    )
    assert _me(forged) == 401


# --- 2. token_version revocation + DB role --------------------------------------


def test_logout_with_token_revokes_every_session():
    email, token_a, _ = _signup()
    token_b = client.post("/api/auth/login", json={"email": email, "password": PASSWORD},
                          headers=_ip()).json()["token"]
    assert _me(token_a) == 200 and _me(token_b) == 200
    res = client.post("/api/auth/logout", headers=_bearer(token_a))
    assert res.status_code == 200 and res.json() == {"message": "Logged out successfully"}
    assert _me(token_a) == 401
    assert _me(token_b) == 401  # logout = sign out everywhere
    fresh = client.post("/api/auth/login", json={"email": email, "password": PASSWORD},
                        headers=_ip()).json()["token"]
    assert _me(fresh) == 200


def test_logout_without_token_still_200():
    res = client.post("/api/auth/logout", headers=_ip())
    assert res.status_code == 200 and res.json() == {"message": "Logged out successfully"}


def test_token_without_tv_claim_works_until_a_bump():
    _, _, user_id = _signup()
    legacy = auth.create_access_token({"sub": user_id, "email": "x@example.com", "role": "user"})
    assert "tv" not in jwt.decode(legacy, options={"verify_signature": False})
    assert _me(legacy) == 200
    auth.bump_token_version(user_id)
    assert _me(legacy) == 401


def test_token_for_deleted_user_is_rejected():
    _, token, user_id = _signup()
    users_collection.delete_one({"_id": ObjectId(user_id)})
    auth.invalidate_user_auth_cache(user_id)
    assert _me(token) == 401


def test_auth_state_is_cached_not_read_every_request(monkeypatch):
    _, token, _ = _signup()
    calls = []
    real = auth._load_user_auth_state
    monkeypatch.setattr(auth, "_load_user_auth_state", lambda uid: calls.append(uid) or real(uid))
    auth.invalidate_user_auth_cache()
    for _ in range(5):
        assert _me(token) == 200
    assert len(calls) == 1


def test_admin_claim_in_token_but_not_db_is_forbidden():
    _, _, user_id = _signup()
    admin_claim = auth.create_access_token({"sub": user_id, "email": "x@example.com", "role": "admin", "tv": 0})
    res = client.post("/api/admin/reset-user-state", json={"user_id": ""}, headers=_bearer(admin_claim))
    assert res.status_code == 403
    users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"role": "admin"}})
    auth.invalidate_user_auth_cache(user_id)
    res = client.post("/api/admin/reset-user-state", json={"user_id": ""}, headers=_bearer(admin_claim))
    assert res.status_code == 400  # past the admin gate, rejected on the empty body


def test_builder_admin_in_production_comes_from_db(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "prod-like-secret-" + uuid.uuid4().hex)
    _, _, user_id = _signup()
    monkeypatch.setenv("ENVIRONMENT", "production")
    admin_claim = auth.create_access_token({"sub": user_id, "email": "x@example.com", "role": "admin", "tv": 0})
    assert client.post("/api/plays", json={}, headers=_bearer(admin_claim)).status_code == 403
    users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"role": "admin"}})
    auth.invalidate_user_auth_cache(user_id)
    assert client.post("/api/plays", json={}, headers=_bearer(admin_claim)).status_code != 403


# --- 4. reset tokens hashed + reset revokes sessions ------------------------------


def test_reset_token_stored_hashed_and_reset_revokes_sessions(monkeypatch):
    email, token, user_id = _signup()
    links = []
    monkeypatch.setattr(auth_routes, "send_password_reset_email", lambda to, link: links.append(link) or True)
    assert client.post("/api/auth/reset-request", json={"email": email}, headers=_ip()).status_code == 200
    reset_token = re.search(r"token=([^&]+)", links[0]).group(1)

    doc = password_reset_tokens_collection.find_one({"user_id": ObjectId(user_id)})
    assert "token" not in doc
    assert doc["token_hash"] == hashlib.sha256(reset_token.encode()).hexdigest()
    assert reset_token not in str(doc)

    res = client.post("/api/auth/reset-password", json={"token": reset_token, "new_password": "NewPassw0rd"},
                      headers=_ip())
    assert res.status_code == 200, res.text
    assert _me(token) == 401
    assert client.post("/api/auth/login", json={"email": email, "password": "NewPassw0rd"},
                       headers=_ip()).status_code == 200


def test_legacy_plaintext_reset_token_no_longer_works():
    _, _, user_id = _signup()
    plaintext = "legacy-" + uuid.uuid4().hex
    password_reset_tokens_collection.insert_one({
        "token": plaintext, "user_id": ObjectId(user_id),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1), "created_at": datetime.now(timezone.utc),
    })
    res = client.post("/api/auth/reset-password", json={"token": plaintext, "new_password": "NewPassw0rd"},
                      headers=_ip())
    assert res.status_code == 400


# --- 5. signup enumeration --------------------------------------------------------


def test_signup_bad_code_does_not_reveal_existing_email(monkeypatch):
    monkeypatch.setenv("IS_ALPHA", "true")
    monkeypatch.setenv("ALPHA_AUTO_SEND_CODES", "false")
    code = f"T{uuid.uuid4().hex[:9].upper()}"
    doc = build_alpha_otp_document(code, now=datetime.now(timezone.utc))
    doc["max_uses"] = 5
    alpha_otps_collection.insert_one(doc)
    email = _email("enum")
    first = client.post("/api/auth/signup", json={"email": email, "password": PASSWORD, "otp_code": code},
                        headers=_ip())
    assert first.status_code == 200, first.text

    bad = client.post("/api/auth/signup", json={"email": email, "password": PASSWORD, "otp_code": "ZZZZZZZZZZ"},
                      headers=_ip())
    assert bad.status_code == 400
    assert bad.json()["detail"] == "Invalid alpha access code"

    good = client.post("/api/auth/signup", json={"email": email, "password": PASSWORD, "otp_code": code},
                       headers=_ip())
    assert good.status_code == 400
    assert good.json()["detail"] == "An account with this email already exists"
    # The "exists" answer did not spend a use of the code.
    assert alpha_otps_collection.find_one({"otp_code": code})["use_count"] == 1


# --- 6. login timing ----------------------------------------------------------------


def test_unknown_email_login_still_runs_a_bcrypt_verify(monkeypatch):
    calls = []
    monkeypatch.setattr(auth_routes, "burn_password_check", lambda pw: calls.append(pw))
    res = client.post("/api/auth/login", json={"email": _email("nobody"), "password": PASSWORD}, headers=_ip())
    assert res.status_code == 401 and res.json()["detail"] == "Invalid email or password"
    assert calls == [PASSWORD]


def test_burn_password_check_really_hashes():
    auth.burn_password_check("anything")
    assert auth._dummy_password_hash and auth._dummy_password_hash.startswith("$2")


# --- 7. bcrypt 72 bytes ---------------------------------------------------------------

LONG = "Aa1" + "x" * 77  # 80 ASCII bytes, passes the other password rules


def test_signup_rejects_password_over_72_bytes():
    res = client.post("/api/auth/signup", json={"email": _email("long"), "password": LONG}, headers=_ip())
    assert res.status_code == 400
    assert "72 bytes" in res.json()["detail"]


def test_signup_counts_bytes_not_characters():
    multibyte = "Aa1" + "é" * 40  # 43 chars, 83 bytes
    res = client.post("/api/auth/signup", json={"email": _email("utf8"), "password": multibyte}, headers=_ip())
    assert res.status_code == 400


def test_reset_rejects_password_over_72_bytes(monkeypatch):
    email, _, _ = _signup()
    links = []
    monkeypatch.setattr(auth_routes, "send_password_reset_email", lambda to, link: links.append(link) or True)
    client.post("/api/auth/reset-request", json={"email": email}, headers=_ip())
    reset_token = re.search(r"token=([^&]+)", links[0]).group(1)
    res = client.post("/api/auth/reset-password", json={"token": reset_token, "new_password": LONG}, headers=_ip())
    assert res.status_code == 400 and "72 bytes" in res.json()["detail"]


def test_legacy_user_with_long_password_can_still_log_in():
    email = _email("legacy")
    # Pre-limit accounts: old bcrypt silently hashed only the first 72 bytes.
    legacy_hash = bcrypt.hashpw(LONG.encode()[:72], bcrypt.gensalt()).decode()
    users_collection.insert_one({"email": email, "password_hash": legacy_hash, "role": "user"})
    ok = client.post("/api/auth/login", json={"email": email, "password": LONG}, headers=_ip())
    assert ok.status_code == 200, ok.text
    assert _me(ok.json()["token"]) == 200
    wrong = client.post("/api/auth/login", json={"email": email, "password": LONG[:-1] + "Q"}, headers=_ip())
    assert wrong.status_code == 200  # byte 80 differs: beyond 72, exactly as before
    assert client.post("/api/auth/login", json={"email": email, "password": "Aa1short"},
                       headers=_ip()).status_code == 401


# --- 3. rate limiting ------------------------------------------------------------------


def _request(headers: dict, client_host="10.9.9.9") -> Request:
    return Request({
        "type": "http", "method": "GET", "path": "/", "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 1234),
    })


def test_rate_limit_key_ignores_spoofed_leftmost_forwarded_for():
    assert rate_limiter.get_remote_address(_request({"X-Forwarded-For": "6.6.6.6, 203.0.113.7"})) == "203.0.113.7"
    assert rate_limiter.get_remote_address(_request({"X-Forwarded-For": "203.0.113.7"})) == "203.0.113.7"
    assert rate_limiter.get_remote_address(
        _request({"X-Real-IP": "198.51.100.4", "X-Forwarded-For": "6.6.6.6, 203.0.113.7"})) == "198.51.100.4"
    assert rate_limiter.get_remote_address(_request({})) == "10.9.9.9"


def test_rotating_fake_leftmost_forwarded_for_does_not_dodge_login_limit():
    edge = f"203.0.113.{uuid.uuid4().int % 250 + 1}"
    statuses = []
    for i in range(12):
        headers = {"X-Forwarded-For": f"6.6.{i}.{i + 1}, {edge}"}
        statuses.append(client.post("/api/auth/login", json={"email": _email("rl"), "password": PASSWORD},
                                    headers=headers).status_code)
    assert statuses[:10] == [401] * 10
    assert 429 in statuses[10:]


@pytest.fixture
def low_default_limit(monkeypatch):
    low = Limiter(key_func=rate_limiter.get_remote_address, default_limits=["3/minute"])
    monkeypatch.setattr(rate_limiter.limiter, "_default_limits", low._default_limits)


def test_default_limit_applies_to_unlimited_routes(low_default_limit):
    headers = _ip()
    statuses = [client.get("/app-config", headers=headers).status_code for _ in range(5)]
    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429 and statuses[4] == 429


def test_health_and_preflight_are_exempt_from_default_limit(low_default_limit):
    headers = _ip()
    assert all(client.get("/health", headers=headers).status_code == 200 for _ in range(8))
    assert all(client.head("/health", headers=headers).status_code == 200 for _ in range(8))
    preflight = {**headers, "Origin": "https://www.geekedoutbasketball.com",
                 "Access-Control-Request-Method": "POST"}
    assert all(client.options("/app-config", headers=preflight).status_code != 429 for _ in range(8))


def test_default_limit_429_keeps_cors_headers(low_default_limit):
    headers = {**_ip(), "Origin": "https://www.geekedoutbasketball.com"}
    last = None
    for _ in range(5):
        last = client.get("/app-config", headers=headers)
    assert last.status_code == 429
    assert last.headers.get("access-control-allow-origin") == "https://www.geekedoutbasketball.com"


def test_heavy_route_limit_is_per_user():
    _, token_a, _ = _signup()
    _, token_b, _ = _signup()
    body = {"franchise_id": str(ObjectId())}
    a = [client.post("/franchise/finish-season", json=body, headers=_bearer(token_a)).status_code
         for _ in range(4)]
    assert a[:3] == [404, 404, 404] and a[3] == 429  # FINISH_SEASON 3/minute
    b = client.post("/franchise/finish-season", json=body, headers=_bearer(token_b)).status_code
    assert b == 404  # a different user has their own budget


# --- 8. unique indexes + dupes script ------------------------------------------------


def _scratch_db():
    return mongomock.MongoClient()[f"authidx-{uuid.uuid4().hex[:8]}"]


def test_unique_email_index_created_when_clean():
    db = _scratch_db()
    db.users.insert_many([{"email": "a@x.com"}, {"email": "b@x.com"}])
    assert indexes.ensure_users_email_index(client=object(), users_collection=db.users) is True
    with pytest.raises(Exception):
        db.users.insert_one({"email": "a@x.com"})


def test_duplicate_data_logs_warning_instead_of_crashing(caplog):
    db = _scratch_db()
    db.users.insert_many([{"email": "a@x.com"}, {"email": "a@x.com"}])
    db.alpha_otps.insert_many([{"otp_code": "ABCDEF1234"}, {"otp_code": "ABCDEF1234"}])
    with caplog.at_level(logging.WARNING):
        assert indexes.ensure_users_email_index(client=object(), users_collection=db.users) is False
        assert indexes.ensure_alpha_otps_code_index(client=object(), alpha_otps_collection=db.alpha_otps) is False
    msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("users.email" in m and "check_auth_dupes" in m for m in msgs)
    assert any("alpha_otps.otp_code" in m for m in msgs)


def test_check_auth_dupes_reports_without_writing():
    db = _scratch_db()
    db.users.insert_many([
        {"email": "a@x.com"}, {"email": "a@x.com"},       # exact: blocks
        {"email": "B@x.com"}, {"email": "b@x.com"},       # case variant
        {"email": "c@x.com"},
    ])
    db.alpha_otps.insert_many([{"otp_code": "CODE000001"}, {"otp_code": "code000001 "}])
    before = (list(db.users.find()), list(db.alpha_otps.find()))
    report = find_auth_dupes(db)
    assert [g["value"] for g in report["users"]["exact"]] == ["a@x.com"]
    assert [g["value"] for g in report["users"]["variant"]] == ["b@x.com"]
    assert report["alpha_otps"]["exact"] == []
    assert [g["value"] for g in report["alpha_otps"]["variant"]] == ["CODE000001"]
    assert blocks_index(report) is True
    assert (list(db.users.find()), list(db.alpha_otps.find())) == before
    assert db.users.index_information().keys() == {"_id_"}
