"""
Alpha access code email templates (Resend).
"""

from __future__ import annotations

import os
from html import escape
from urllib.parse import urlparse

from BackEnd.utils.resend_sender import ALPHA_EMAIL_FROM, send_resend_html_email


def _signup_link_base_url() -> str:
    return os.getenv(
        "SIGNUP_LINK_BASE_URL",
        "https://www.geekedoutbasketball.com/signup.html",
    )


def get_alpha_badge_url() -> str:
    override = os.getenv("ALPHA_BADGE_URL")
    if override:
        return override.strip()
    parsed = urlparse(_signup_link_base_url())
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return f"{origin}/images/gob-alpha-badge.png"


def _signature_html() -> str:
    badge_url = escape(get_alpha_badge_url())
    return (
        "<p>Jamie</p>"
        "<p><em>PS — reply anytime with feedback. I read every message.</em></p>"
        f'<p><img src="{badge_url}" alt="GOB Alpha" width="300" /></p>'
    )


def build_alpha_welcome_html(*, otp_code: str) -> str:
    safe_code = escape(otp_code)
    signup_url = escape(_signup_link_base_url().rstrip("/"))
    return (
        "<p>Hey Coach,</p>"
        "<p>Welcome to the Geeked Out Basketball alpha. Thanks for your patience while we "
        "continue to build the experience. We've just wrapped a major round of feature updates and "
        "are excited to release the next wave of alpha access codes. Yours is below.</p>"
        "<p>So jump in, start coaching, and start racking up titles and Geek Points!</p>"
        f'<p>Head to <a href="{signup_url}">{signup_url}</a> to create your account.</p>'
        "<p><strong>Your Access Code:</strong></p>"
        f'<p style="font-size:20px;font-weight:bold;letter-spacing:1px;">{safe_code}</p>'
        + _signature_html()
    )


def build_alpha_waitlist_html() -> str:
    return (
        "<p>Hey Coach,</p>"
        "<p>Thanks for requesting alpha access. We're at capacity right now, but you're on "
        "the list — we'll email your access code as soon as a spot opens up.</p>"
        "<p>Thanks for your patience.</p>"
        + _signature_html()
    )


def send_alpha_welcome_email(email: str, otp_code: str) -> bool:
    html = build_alpha_welcome_html(otp_code=otp_code)
    return send_resend_html_email(
        to=[email],
        subject="Your Geeked Out Basketball Alpha Access Code",
        html=html,
        from_email=ALPHA_EMAIL_FROM,
    )


def send_alpha_waitlist_email(email: str) -> bool:
    html = build_alpha_waitlist_html()
    return send_resend_html_email(
        to=[email],
        subject="Geeked Out Basketball Alpha — Code Coming Soon",
        html=html,
        from_email=ALPHA_EMAIL_FROM,
    )
