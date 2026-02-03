"""
Minimal email sending for password reset (Step 11).

Uses SendGrid v3 API. Set SENDGRID_API_KEY and RESET_EMAIL_FROM in environment.
If SENDGRID_API_KEY is not set, send_password_reset_email returns False and no request is made.
"""

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
RESET_EMAIL_FROM = os.getenv("RESET_EMAIL_FROM", "noreply@geekedoutbasketball.com")
RESET_LINK_BASE_URL = os.getenv("RESET_LINK_BASE_URL", "https://www.geekedoutbasketball.com")


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """
    Send a single password reset email via SendGrid.

    Args:
        to_email: Recipient email address.
        reset_link: Full URL for the user to click (e.g. https://www.../reset-password.html?token=...).

    Returns:
        True if sent successfully, False if not configured or send failed.
    """
    if not SENDGRID_API_KEY:
        logger.warning("[RESET] SENDGRID_API_KEY not set - skipping password reset email")
        return False

    to_redacted = (to_email[:2] + "***@" + to_email.split("@")[-1]) if "@" in to_email else "***"
    from_redacted = "***@" + RESET_EMAIL_FROM.split("@")[-1] if "@" in RESET_EMAIL_FROM else "***"
    logger.warning("[RESET] SendGrid: from=%s to=%s", from_redacted, to_redacted)
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": RESET_EMAIL_FROM, "name": "Geeked Out Basketball"},
        "subject": "Reset your Geeked Out Basketball password",
        "content": [
            {
                "type": "text/plain",
                "value": (
                    "You requested a password reset for Geeked Out Basketball.\n\n"
                    "Click the link below to set a new password (link expires in 1 hour):\n\n"
                    f"{reset_link}\n\n"
                    "If you didn't request this, you can ignore this email."
                ),
            },
        ],
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {SENDGRID_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if resp.status_code >= 200 and resp.status_code < 300:
            logger.warning("[RESET] SendGrid mail/send succeeded (status=%s)", resp.status_code)
            return True
        logger.warning("[RESET] SendGrid returned %s: %s", resp.status_code, resp.text[:300])
        return False
    except Exception as e:
        logger.exception("[RESET] SendGrid request failed: %s", e)
        return False
