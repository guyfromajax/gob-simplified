"""Tests for multi-use alpha access codes, request queue, and check endpoint."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from BackEnd.api import auth_routes
from BackEnd.api.api import app
from BackEnd.db import (
    access_code_requests_collection,
    alpha_access_requests_collection,
    alpha_otps_collection,
)
from BackEnd.utils.otp_validator import inspect_code, release_code, reserve_code
from scripts.generate_alpha_otps import build_alpha_otp_document


client = TestClient(app)


def _headers() -> dict[str, str]:
    token = uuid.uuid4().hex
    return {"X-Forwarded-For": f"10.{int(token[0:2], 16)}.{int(token[2:4], 16)}.{int(token[4:6], 16)}"}


def _code() -> str:
    return f"T{uuid.uuid4().hex[:9].upper()}"


def _email(prefix: str = "coach") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def _insert_otp(**overrides):
    now = datetime.now(timezone.utc)
    code = overrides.pop("otp_code", _code())
    doc = build_alpha_otp_document(code, now=now)
    doc.update(overrides)
    alpha_otps_collection.insert_one(doc)
    return doc["otp_code"]


@pytest.fixture(autouse=True)
def _alpha_mode(monkeypatch):
    monkeypatch.setenv("IS_ALPHA", "true")
    monkeypatch.setenv("ALPHA_AUTO_SEND_CODES", "false")
    monkeypatch.setattr(auth_routes, "send_alpha_welcome_email", lambda *a, **k: True)
    monkeypatch.setattr(auth_routes, "send_alpha_waitlist_email", lambda *a, **k: True)
    monkeypatch.setattr(auth_routes, "_trigger_password_reset_for_email", lambda *a, **k: None)


def test_reserve_and_release_restores_spot():
    code = _insert_otp(max_uses=1, use_count=0)
    email = _email()
    ok, reason = reserve_code(code, email)
    assert ok is True
    assert reason is None
    doc = alpha_otps_collection.find_one({"otp_code": code})
    assert doc["use_count"] == 1
    assert doc["used"] is True
    assert doc["redemptions"][0]["email"] == email
    assert doc["used_by_email"] == email

    assert release_code(code, email) is True
    doc = alpha_otps_collection.find_one({"otp_code": code})
    assert doc["use_count"] == 0
    assert doc["used"] is False
    assert doc["redemptions"] == []
    assert doc.get("used_by_email") is None

    other = _email("other")
    ok, reason = reserve_code(code, other)
    assert ok is True
    doc = alpha_otps_collection.find_one({"otp_code": code})
    assert doc["used_by_email"] == other


def test_concurrent_last_spot_contention():
    code = _insert_otp(max_uses=1, use_count=0)

    def attempt(i: int):
        return reserve_code(code, f"contend-{i}-{uuid.uuid4().hex[:6]}@example.com")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    successes = [item for item in results if item[0]]
    exhausted = [item for item in results if item == (False, "exhausted")]
    assert len(successes) == 1
    assert len(exhausted) == 7
    doc = alpha_otps_collection.find_one({"otp_code": code})
    assert doc["use_count"] == 1
    assert doc["used"] is True
    assert len(doc["redemptions"]) == 1


def test_inspect_reasons_invalid_exhausted_inactive():
    assert inspect_code("NOPEXXXX") == (False, "invalid")
    assert inspect_code("AB") == (False, "invalid")

    exhausted = _insert_otp(max_uses=1, use_count=1, used=False)
    assert inspect_code(exhausted) == (False, "exhausted")
    assert reserve_code(exhausted, _email()) == (False, "exhausted")

    inactive = _insert_otp(active=False, used=False, use_count=0, max_uses=1)
    assert inspect_code(inactive) == (False, "inactive")
    assert reserve_code(inactive, _email()) == (False, "inactive")

    valid = _insert_otp()
    assert inspect_code(valid) == (True, None)
    assert inspect_code(valid.lower()) == (True, None)


def test_legacy_used_true_doc_rejected():
    code = _code()
    alpha_otps_collection.insert_one(
        {
            "otp_code": code,
            "used": True,
            "used_by_email": "old@example.com",
            "used_at": datetime.now(timezone.utc),
        }
    )
    assert inspect_code(code) == (False, "exhausted")
    assert reserve_code(code, _email()) == (False, "exhausted")


def test_check_access_code_endpoint():
    valid = _insert_otp()
    headers = _headers()
    response = client.post(
        "/api/auth/check-access-code",
        json={"code": valid.lower()},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == {"valid": True, "reason": None}

    exhausted = _insert_otp(max_uses=1, use_count=1, used=True)
    response = client.post(
        "/api/auth/check-access-code",
        json={"code": exhausted},
        headers=_headers(),
    )
    assert response.json() == {"valid": False, "reason": "exhausted"}

    inactive = _insert_otp(active=False)
    response = client.post(
        "/api/auth/check-access-code",
        json={"code": inactive},
        headers=_headers(),
    )
    assert response.json() == {"valid": False, "reason": "inactive"}

    response = client.post(
        "/api/auth/check-access-code",
        json={"code": "ZZZZZZZZZZ"},
        headers=_headers(),
    )
    assert response.json() == {"valid": False, "reason": "invalid"}


def test_check_access_code_rate_limit():
    headers = {"X-Forwarded-For": f"203.0.113.{uuid.uuid4().int % 200 + 1}"}
    statuses = []
    for _ in range(11):
        response = client.post(
            "/api/auth/check-access-code",
            json={"code": "ZZZZZZZZZZ"},
            headers=headers,
        )
        statuses.append(response.status_code)
    assert 429 in statuses
    assert statuses.count(200) == 10


def test_request_upsert_and_dedupe():
    email = _email("queue")
    first = client.post(
        "/api/auth/request-access-code",
        json={"email": email, "source": "reddit"},
        headers=_headers(),
    )
    assert first.status_code == 200
    assert first.json()["status"] == "queued"

    second = client.post(
        "/api/auth/request-access-code",
        json={"email": email, "source": "twitter"},
        headers=_headers(),
    )
    assert second.json()["status"] == "queued"

    docs = list(alpha_access_requests_collection.find({"email": email}))
    assert len(docs) == 1
    assert docs[0]["request_count"] == 2
    assert docs[0]["status"] == "pending"
    assert docs[0]["source"] == "reddit"

    logs = list(access_code_requests_collection.find({"email": email}))
    assert len(logs) == 2
    assert {row["status"] for row in logs} == {"queued"}


def test_granted_resend_path(monkeypatch):
    email = _email("granted")
    code = _insert_otp()
    now = datetime.now(timezone.utc)
    alpha_access_requests_collection.insert_one(
        {
            "email": email,
            "status": "granted",
            "otp_code": code,
            "first_requested_at": now,
            "last_requested_at": now,
            "request_count": 1,
            "source": "manual",
            "granted_at": now,
            "granted_by": "jamie",
        }
    )
    sent = []
    monkeypatch.setattr(
        auth_routes,
        "send_alpha_welcome_email",
        lambda to_email, otp: sent.append((to_email, otp)) or True,
    )
    response = client.post(
        "/api/auth/request-access-code",
        json={"email": email},
        headers=_headers(),
    )
    assert response.json()["status"] == "queued"
    assert sent == [(email, code)]
    logs = list(access_code_requests_collection.find({"email": email}))
    assert logs[-1]["status"] == "resent"


def test_signup_marks_request_registered():
    email = _email("signup")
    code = _insert_otp()
    now = datetime.now(timezone.utc)
    alpha_access_requests_collection.insert_one(
        {
            "email": email,
            "status": "granted",
            "otp_code": code,
            "first_requested_at": now,
            "last_requested_at": now,
            "request_count": 1,
            "source": "manual",
        }
    )
    response = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "Password1", "otp_code": code.lower()},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    doc = alpha_access_requests_collection.find_one({"email": email})
    assert doc["status"] == "registered"
    assert doc["otp_code"] == code
    otp = alpha_otps_collection.find_one({"otp_code": code})
    assert otp["used"] is True
    assert otp["use_count"] == 1
    assert otp["used_by_email"] == email


def test_signup_releases_code_if_user_create_fails(monkeypatch):
    email = _email("failcreate")
    code = _insert_otp()

    def boom(*_args, **_kwargs):
        raise RuntimeError("insert failed")

    monkeypatch.setattr(auth_routes.users_collection, "insert_one", boom)
    with pytest.raises(RuntimeError, match="insert failed"):
        client.post(
            "/api/auth/signup",
            json={"email": email, "password": "Password1", "otp_code": code},
            headers=_headers(),
        )
    otp = alpha_otps_collection.find_one({"otp_code": code})
    assert otp["use_count"] == 0
    assert otp["used"] is False
    assert otp["redemptions"] == []


def test_signup_exhausted_when_code_taken():
    code = _insert_otp(max_uses=1)
    first = client.post(
        "/api/auth/signup",
        json={"email": _email("first"), "password": "Password1", "otp_code": code},
        headers=_headers(),
    )
    assert first.status_code == 200
    second = client.post(
        "/api/auth/signup",
        json={"email": _email("second"), "password": "Password1", "otp_code": code},
        headers=_headers(),
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "All spots on this code are claimed."
