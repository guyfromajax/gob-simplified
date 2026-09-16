"""Tests for alpha access code email automation."""

from BackEnd.utils.alpha_access_email import build_alpha_welcome_html, get_alpha_badge_url
from BackEnd.utils.used_otp_codes_markdown import parse_used_otp_codes_from_text
from BackEnd.api import auth_routes
from BackEnd.api.api import app
from BackEnd.db import alpha_access_requests_collection, alpha_otps_collection
from fastapi.testclient import TestClient
from scripts.generate_alpha_otps import build_alpha_otp_document
from datetime import datetime, timezone
import uuid


SAMPLE_MARKDOWN = """
# 35 Unused OTPs

MX6DZGFJD5
CAW5S6VZEG

WR6KD2N9HU - leftcheek08@gmail.com

Reddit Round 2
7SABBXAN7F
B58UJ234J9

April 26 Codes Emailed
567356CN6G - used
UB9TXRZNBA - used
"""

client = TestClient(app)


def test_parse_used_otp_codes_ignores_headers_and_extracts_codes():
    codes = parse_used_otp_codes_from_text(SAMPLE_MARKDOWN)
    assert codes == [
        "MX6DZGFJD5",
        "CAW5S6VZEG",
        "WR6KD2N9HU",
        "7SABBXAN7F",
        "B58UJ234J9",
        "567356CN6G",
        "UB9TXRZNBA",
    ]


def test_welcome_html_includes_otp_and_escapes(monkeypatch):
    monkeypatch.setenv("SIGNUP_LINK_BASE_URL", "https://gob-test.netlify.app/signup.html")
    html = build_alpha_welcome_html(otp_code="ABC<script>")
    assert "ABC&lt;script&gt;" in html
    assert "https://gob-test.netlify.app/signup.html" in html


def test_badge_url_uses_netlify_images_path(monkeypatch):
    monkeypatch.setenv("SIGNUP_LINK_BASE_URL", "https://gob-test.netlify.app/signup.html")
    monkeypatch.delenv("ALPHA_BADGE_URL", raising=False)
    assert get_alpha_badge_url() == "https://gob-test.netlify.app/images/gob-alpha-badge.png"


def test_auto_send_flag_defaults_false_sends_waitlist_not_code(monkeypatch):
    monkeypatch.delenv("ALPHA_AUTO_SEND_CODES", raising=False)
    sent = []
    monkeypatch.setattr(auth_routes, "send_alpha_welcome_email", lambda *a, **k: sent.append("welcome") or True)
    monkeypatch.setattr(auth_routes, "send_alpha_waitlist_email", lambda *a, **k: sent.append("waitlist") or True)
    email = f"flag-off-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/auth/request-access-code",
        json={"email": email},
        headers={"X-Forwarded-For": "192.0.2.40"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert sent == ["waitlist"]
    queued = alpha_access_requests_collection.find_one({"email": email})
    assert queued["status"] == "pending"
    assert queued["request_count"] == 1

    second = client.post(
        "/api/auth/request-access-code",
        json={"email": email},
        headers={"X-Forwarded-For": "192.0.2.40"},
    )
    assert second.status_code == 200
    assert sent == ["waitlist"]


def test_auto_send_flag_true_keeps_legacy_email_path(monkeypatch):
    monkeypatch.setenv("ALPHA_AUTO_SEND_CODES", "true")
    sent = []
    monkeypatch.setattr(auth_routes, "send_alpha_welcome_email", lambda email, code: sent.append(code) or True)
    monkeypatch.setattr(auth_routes, "send_alpha_waitlist_email", lambda *a, **k: sent.append("waitlist") or True)
    code = f"F{uuid.uuid4().hex[:9].upper()}"
    now = datetime.now(timezone.utc)
    alpha_otps_collection.insert_one(
        build_alpha_otp_document(code, now=now, sent=False)
    )
    email = f"flag-on-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/auth/request-access-code",
        json={"email": email},
        headers={"X-Forwarded-For": "192.0.2.41"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sent"
    claimed = alpha_otps_collection.find_one({"sent_to_email": email})
    assert claimed is not None
    assert sent == [claimed["otp_code"]]
    assert alpha_access_requests_collection.find_one({"email": email}) is None



SAMPLE_MARKDOWN = """
# 35 Unused OTPs

MX6DZGFJD5
CAW5S6VZEG

WR6KD2N9HU - leftcheek08@gmail.com

Reddit Round 2
7SABBXAN7F
B58UJ234J9

April 26 Codes Emailed
567356CN6G - used
UB9TXRZNBA - used
"""


def test_parse_used_otp_codes_ignores_headers_and_extracts_codes():
    codes = parse_used_otp_codes_from_text(SAMPLE_MARKDOWN)
    assert codes == [
        "MX6DZGFJD5",
        "CAW5S6VZEG",
        "WR6KD2N9HU",
        "7SABBXAN7F",
        "B58UJ234J9",
        "567356CN6G",
        "UB9TXRZNBA",
    ]


def test_welcome_html_includes_otp_and_escapes(monkeypatch):
    monkeypatch.setenv("SIGNUP_LINK_BASE_URL", "https://gob-test.netlify.app/signup.html")
    html = build_alpha_welcome_html(otp_code="ABC<script>")
    assert "ABC&lt;script&gt;" in html
    assert "https://gob-test.netlify.app/signup.html" in html


def test_badge_url_uses_netlify_images_path(monkeypatch):
    monkeypatch.setenv("SIGNUP_LINK_BASE_URL", "https://gob-test.netlify.app/signup.html")
    monkeypatch.delenv("ALPHA_BADGE_URL", raising=False)
    assert get_alpha_badge_url() == "https://gob-test.netlify.app/images/gob-alpha-badge.png"
