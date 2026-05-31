"""Tests for alpha access code email automation."""

from BackEnd.utils.alpha_access_email import build_alpha_welcome_html, get_alpha_badge_url
from BackEnd.utils.used_otp_codes_markdown import parse_used_otp_codes_from_text


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
