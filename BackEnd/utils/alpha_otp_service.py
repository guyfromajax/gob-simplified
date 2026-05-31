"""
Alpha OTP pool management for access code emails.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import ReturnDocument

from BackEnd.db import alpha_otps_collection


def count_available_otps() -> int:
    return alpha_otps_collection.count_documents({"used": False, "sent": False})


def find_otp_for_email(email: str) -> Optional[dict[str, Any]]:
    """Existing reservation: sent to this email, not yet used at signup."""
    return alpha_otps_collection.find_one(
        {
            "sent_to_email": email,
            "sent": True,
            "used": False,
        }
    )


def claim_otp_for_email(email: str) -> Optional[str]:
    """
    Atomically reserve the oldest available OTP for an email.

    Returns otp_code or None if pool is empty.
    """
    now = datetime.now(timezone.utc)
    doc = alpha_otps_collection.find_one_and_update(
        {"used": False, "sent": False},
        {"$set": {"sent": True, "sent_to_email": email, "sent_at": now}},
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        return None
    return doc.get("otp_code")


def release_otp_claim(otp_code: str) -> bool:
    """Rollback a failed send so the OTP returns to the pool."""
    result = alpha_otps_collection.update_one(
        {"otp_code": otp_code, "sent": True, "used": False},
        {"$set": {"sent": False, "sent_to_email": None, "sent_at": None}},
    )
    return result.modified_count == 1
