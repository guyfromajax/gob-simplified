"""
Email suppression + unsubscribe support for marketing/re-engagement sends.

- Stateless HMAC unsubscribe tokens (no per-user token storage).
- `email_unsubscribes` collection is the suppression source of truth.
- Helpers to build the recipient suppression set for a campaign.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

from BackEnd.db import db

try:
    from BackEnd.utils.auth import JWT_SECRET_KEY as _JWT_SECRET_KEY
except Exception:  # pragma: no cover - auth import is always available in app context
    _JWT_SECRET_KEY = "dev-secret"

UNSUBSCRIBE_LINK_BASE_URL = os.getenv(
    "UNSUBSCRIBE_LINK_BASE_URL", "https://www.geekedoutbasketball.com"
)

unsubscribes_collection = db["email_unsubscribes"]
reengagement_sends_collection = db["reengagement_sends"]


def _secret() -> bytes:
    return (os.getenv("EMAIL_UNSUB_SECRET") or _JWT_SECRET_KEY).encode("utf-8")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def unsubscribe_token(email: str) -> str:
    """Tamper-proof token bound to the (normalized) email."""
    msg = normalize_email(email).encode("utf-8")
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()


def verify_unsubscribe_token(email: str, token: str) -> bool:
    return hmac.compare_digest(unsubscribe_token(email), (token or ""))


def unsubscribe_url(email: str) -> str:
    from urllib.parse import quote

    e = normalize_email(email)
    return (
        f"{UNSUBSCRIBE_LINK_BASE_URL.rstrip('/')}/api/email/unsubscribe"
        f"?e={quote(e)}&t={unsubscribe_token(e)}"
    )


def record_unsubscribe(email: str, *, source: str = "link") -> None:
    e = normalize_email(email)
    if not e:
        return
    unsubscribes_collection.update_one(
        {"email": e},
        {
            "$setOnInsert": {
                "email": e,
                "unsubscribed_at": datetime.now(timezone.utc),
                "source": source,
            }
        },
        upsert=True,
    )


def is_unsubscribed(email: str) -> bool:
    return unsubscribes_collection.count_documents({"email": normalize_email(email)}, limit=1) > 0


def unsubscribed_email_set() -> set[str]:
    return {d["email"] for d in unsubscribes_collection.find({}, {"email": 1}) if d.get("email")}


def recent_alpha_send_email_set(*, days: int = 7) -> set[str]:
    """Emails that received an alpha welcome email within `days` (suppress these)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = db["access_code_requests"].find(
        {"status": "sent", "sent_at": {"$gte": cutoff}}, {"email": 1}
    )
    return {normalize_email(d.get("email", "")) for d in cursor if d.get("email")}


def campaign_sent_email_set(campaign: str) -> set[str]:
    """Emails already sent this campaign (idempotent re-runs)."""
    cursor = reengagement_sends_collection.find({"campaign": campaign}, {"email": 1})
    return {d["email"] for d in cursor if d.get("email")}


def record_campaign_send(email: str, campaign: str) -> None:
    e = normalize_email(email)
    reengagement_sends_collection.update_one(
        {"email": e, "campaign": campaign},
        {"$setOnInsert": {"email": e, "campaign": campaign, "sent_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
