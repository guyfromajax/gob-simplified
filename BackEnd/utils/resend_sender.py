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
ALPHA_EMAIL_FROM = os.getenv("ALPHA_EMAIL_FROM", FEEDBACK_FROM_EMAIL)


def send_resend_html_email(*, to: list[str], subject: str, html: str, from_email: str | None = None) -> bool:
    """Send a single HTML email via Resend."""
    if not RESEND_API_KEY:
        logger.warning("[RESEND] RESEND_API_KEY not set - skipping email send")
        return False

    payload = {
        "from": from_email or ALPHA_EMAIL_FROM,
        "to": to,
        "subject": subject,
        "html": html,
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
            logger.warning("[RESEND] send succeeded (status=%s subject=%s)", resp.status_code, subject)
            return True
        logger.warning("[RESEND] returned %s: %s", resp.status_code, resp.text[:300])
        return False
    except Exception as exc:
        logger.exception("[RESEND] request failed: %s", exc)
        return False


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

    html = (
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
    )
    return send_resend_html_email(
        to=[FEEDBACK_TO_EMAIL],
        subject=f"[GOB Feedback] {safe_category}",
        html=html,
        from_email=FEEDBACK_FROM_EMAIL,
    )


# Human-readable labels for the 8 rating questions in the alpha survey email.
_ALPHA_RATING_LABELS = {
    "live_gameplay": "Live Gameplay",
    "between_games": "The Experience Between Games",
    "training": "Training",
    "franchise_mode": "Franchise Mode",
    "high_school_setting": "High School Setting",
    "onboarding": "Onboarding Experience",
    "game_length": "Time to play a single game",
    "learning_curve": "Learning curve",
}


def send_alpha_feedback_email(
    *,
    ratings: dict,
    optional_notes: dict,
    favorite: str,
    least_favorite: str,
    would_recommend: bool,
    context: dict,
    user_label: str = "",
) -> bool:
    """Send the 11-question alpha survey to the team inbox (FEEDBACK_TO_EMAIL).

    Goes to jamie@geekedoutgames.com (env-overridable); never to the submitter.
    Best-effort: returns False (and no-ops) when Resend isn't configured.
    """
    if not RESEND_API_KEY:
        logger.warning("[ALPHA_FEEDBACK] RESEND_API_KEY not set - skipping survey email send")
        return False

    notes = optional_notes or {}
    rows = []
    for key, label in _ALPHA_RATING_LABELS.items():
        val = escape(str((ratings or {}).get(key, "—")))
        note = notes.get(key)
        note_html = f"<br><em>Note: {escape(str(note))}</em>" if note else ""
        rows.append(f"<p><strong>{escape(label)}:</strong> {val}{note_html}</p>")

    safe_fav = escape(favorite or "").replace("\n", "<br>")
    safe_least = escape(least_favorite or "").replace("\n", "<br>")
    rec = "Yes" if would_recommend else "No"
    safe_user = escape(str((context or {}).get("user", "") or user_label or ""))
    safe_agent = escape(str((context or {}).get("user_agent", "")))
    safe_ip = escape(str((context or {}).get("ip", "")))
    safe_ver = escape(str((context or {}).get("app_version", "")))

    html = (
        "<h2>New Alpha Feedback Survey</h2>"
        f"<p><strong>User:</strong> {safe_user}</p>"
        + "".join(rows)
        + "<hr>"
        f"<p><strong>Favorite thing about GOB:</strong><br>{safe_fav}</p>"
        f"<p><strong>Least favorite thing about GOB:</strong><br>{safe_least}</p>"
        f"<p><strong>Would recommend to a friend:</strong> {rec}</p>"
        "<hr>"
        f"<p><strong>App version:</strong> {safe_ver}</p>"
        f"<p><strong>IP:</strong> {safe_ip}</p>"
        f"<p><strong>User Agent:</strong> {safe_agent}</p>"
    )
    return send_resend_html_email(
        to=[FEEDBACK_TO_EMAIL],
        subject="[GOB Alpha Survey] New submission",
        html=html,
        from_email=FEEDBACK_FROM_EMAIL,
    )
