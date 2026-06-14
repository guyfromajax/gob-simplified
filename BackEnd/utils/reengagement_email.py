"""
Re-engagement ("come back and play") email — marketing send to existing users.

CAN-SPAM compliant: every email carries an unsubscribe link, List-Unsubscribe
headers, and a physical mailing address (GOB_MAILING_ADDRESS, default baked in).

Copy source of truth: _documentation_master/projects/Website_Copy/reengagement_email.md
"""

from __future__ import annotations

import os
from html import escape

from BackEnd.utils.email_suppression import unsubscribe_url
from BackEnd.utils.resend_sender import ALPHA_EMAIL_FROM, send_resend_html_email

REENGAGEMENT_SUBJECT = "The new Geeked Out Basketball is here"

# Physical address required for marketing email (CAN-SPAM). Env-overridable.
_DEFAULT_MAILING_ADDRESS = "Geeked Out Games\n1001 S Broad St\nPhiladelphia, PA 19147"


def _signup_link_base_url() -> str:
    return os.getenv("SIGNUP_LINK_BASE_URL", "https://www.geekedoutbasketball.com/signup.html")


def _app_origin() -> str:
    from urllib.parse import urlparse

    p = urlparse(_signup_link_base_url())
    return f"{p.scheme}://{p.netloc}"


def _mailing_address() -> str:
    return os.getenv("GOB_MAILING_ADDRESS", _DEFAULT_MAILING_ADDRESS)


def build_reengagement_html(*, email: str) -> str:
    """Build the HTML body for one recipient (unsubscribe link is per-email)."""
    play_url = escape(_app_origin())
    unsub = escape(unsubscribe_url(email))
    address = escape(_mailing_address()).replace("\n", "<br>")

    body = (
        "<p>Hey Coach,</p>"
        "<p>It's been a minute. While you were gone, we tore the game apart and put it back "
        "together better.</p>"
        "<p>Smoother animation that actually feels like basketball. A tutorial system that gets "
        "you running fast. Deeper recruiting, practice squads, personalized coaching analysis, "
        "a community leaderboard to prove you belong at the top, and much much more.</p>"
        "<p>The court's open. Pick a program, build a roster, and go chase a title.</p>"
        f'<p><a href="{play_url}">Play now »</a></p>'
        "<p>— Jamie</p>"
        "<p><em>PS — if you've got an old franchise linked to your account, start fresh. The new "
        "build is a different game, and you'll want to feel all of it from day one.</em></p>"
    )

    footer = (
        '<hr style="margin-top:28px;border:none;border-top:1px solid #ddd;">'
        '<p style="font-size:12px;color:#888;">'
        f"You're receiving this because you have a Geeked Out Basketball account.<br>"
        f"{address}<br>"
        f'<a href="{unsub}">Unsubscribe</a>'
        "</p>"
    )
    return body + footer


def _unsubscribe_headers(email: str) -> dict:
    url = unsubscribe_url(email)
    return {
        "List-Unsubscribe": f"<{url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def send_reengagement_email(email: str) -> bool:
    html = build_reengagement_html(email=email)
    return send_resend_html_email(
        to=[email],
        subject=REENGAGEMENT_SUBJECT,
        html=html,
        from_email=ALPHA_EMAIL_FROM,
        headers=_unsubscribe_headers(email),
    )
