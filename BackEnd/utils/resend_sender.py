"""
Resend email sender utilities.
"""

import logging
import os
from html import escape

import httpx

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FEEDBACK_FROM_EMAIL = os.getenv("FEEDBACK_FROM_EMAIL", "jamie@geekedoutgames.com")
FEEDBACK_TO_EMAIL = os.getenv("FEEDBACK_TO_EMAIL", "jamie@geekedoutgames.com")


def send_feedback_email(*, message: str, category: str, reporter_email: str, context: dict) -> bool:
    """
    Send a feedback email through Resend.

    Returns:
        bool: True when sent successfully, else False.
    """
    if not RESEND_API_KEY:
        logger.warning("[FEEDBACK] RESEND_API_KEY not set - skipping feedback email send")
        return False

    safe_category = escape(category or "general")
    safe_reporter = escape(reporter_email or "not provided")
    safe_message = escape(message or "").replace("\n", "<br>")
    safe_path = escape(str((context or {}).get("path", "")))
    safe_url = escape(str((context or {}).get("url", "")))
    safe_user = escape(str((context or {}).get("user", "")))
    safe_mode = escape(str((context or {}).get("mode", "")))
    safe_agent = escape(str((context or {}).get("user_agent", "")))

    payload = {
        "from": FEEDBACK_FROM_EMAIL,
        "to": [FEEDBACK_TO_EMAIL],
        "subject": f"[GOB Feedback] {safe_category}",
        "html": (
            "<h2>New Feedback Submission</h2>"
            f"<p><strong>Category:</strong> {safe_category}</p>"
            f"<p><strong>Reporter Email:</strong> {safe_reporter}</p>"
            f"<p><strong>Mode:</strong> {safe_mode}</p>"
            f"<p><strong>User:</strong> {safe_user}</p>"
            f"<p><strong>Path:</strong> {safe_path}</p>"
            f"<p><strong>URL:</strong> {safe_url}</p>"
            f"<p><strong>User Agent:</strong> {safe_agent}</p>"
            "<hr>"
            f"<p>{safe_message}</p>"
        ),
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if 200 <= resp.status_code < 300:
            logger.warning("[FEEDBACK] Resend send succeeded (status=%s)", resp.status_code)
            return True
        logger.warning("[FEEDBACK] Resend returned %s: %s", resp.status_code, resp.text[:300])
        return False
    except Exception as exc:
        logger.exception("[FEEDBACK] Resend request failed: %s", exc)
        return False
