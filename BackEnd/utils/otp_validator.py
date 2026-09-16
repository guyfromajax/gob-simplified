"""
OTP Validation Utility

Alpha access codes are redeemable when:
  active != false AND used != true AND use_count < max_uses
Missing max_uses is treated as 1. A used:true document is full.

Signup claims a spot with reserve_code() before creating the user, then
release_code() if user creation fails.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from pymongo import ReturnDocument

from BackEnd.db import alpha_otps_collection

MIN_OTP_LENGTH = 6


def is_alpha_mode() -> bool:
    return os.getenv("IS_ALPHA", "false").lower() == "true"


def normalize_otp_code(otp_code: Optional[str]) -> str:
    if not otp_code:
        return ""
    return otp_code.strip().upper()


def _max_uses(doc: dict[str, Any]) -> int:
    value = doc.get("max_uses")
    if isinstance(value, bool):
        return 1
    if isinstance(value, int) and value >= 1:
        return value
    if isinstance(value, float) and value >= 1:
        return int(value)
    return 1


def _use_count(doc: dict[str, Any]) -> int:
    value = doc.get("use_count")
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value >= 0:
        return int(value)
    return 0


def is_code_redeemable(doc: dict[str, Any]) -> bool:
    if doc.get("active") is False:
        return False
    if doc.get("used") is True:
        return False
    return _use_count(doc) < _max_uses(doc)


def inspect_code(otp_code: str) -> Tuple[bool, Optional[str]]:
    """Read-only check. Returns (True, None) or (False, reason)."""
    code = normalize_otp_code(otp_code)
    if len(code) < MIN_OTP_LENGTH:
        return False, "invalid"

    doc = alpha_otps_collection.find_one({"otp_code": code})
    if not doc:
        return False, "invalid"
    if doc.get("active") is False:
        return False, "inactive"
    if not is_code_redeemable(doc):
        return False, "exhausted"
    return True, None


def _redeemable_filter(code: str) -> dict[str, Any]:
    return {
        "otp_code": code,
        "active": {"$ne": False},
        "used": {"$ne": True},
        "$expr": {
            "$lt": [
                {"$ifNull": ["$use_count", 0]},
                {"$ifNull": ["$max_uses", 1]},
            ]
        },
    }


def reserve_code(otp_code: str, email: str) -> Tuple[bool, Optional[str]]:
    """
    Atomically claim one use of a code.

    Returns (True, None) on success, or (False, "invalid"|"exhausted"|"inactive").
    Two concurrent callers cannot both take the last remaining spot.
    """
    code = normalize_otp_code(otp_code)
    if len(code) < MIN_OTP_LENGTH:
        return False, "invalid"
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return False, "invalid"

    existing = alpha_otps_collection.find_one({"otp_code": code})
    if not existing:
        return False, "invalid"
    if existing.get("active") is False:
        return False, "inactive"

    now = datetime.now(timezone.utc)
    pipeline = [
        {
            "$set": {
                "use_count": {"$add": [{"$ifNull": ["$use_count", 0]}, 1]},
                "redemptions": {
                    "$concatArrays": [
                        {"$ifNull": ["$redemptions", []]},
                        [{"email": normalized_email, "used_at": now}],
                    ]
                },
                "used_by_email": {"$ifNull": ["$used_by_email", normalized_email]},
                "used_at": {"$ifNull": ["$used_at", now]},
            }
        },
        {
            "$set": {
                "used": {
                    "$gte": ["$use_count", {"$ifNull": ["$max_uses", 1]}]
                }
            }
        },
    ]
    doc = alpha_otps_collection.find_one_and_update(
        _redeemable_filter(code),
        pipeline,
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        return False, "exhausted"
    return True, None


def release_code(otp_code: str, email: str) -> bool:
    """Roll back one reservation after a failed user create."""
    code = normalize_otp_code(otp_code)
    normalized_email = (email or "").strip().lower()
    if not code or not normalized_email:
        return False

    result = alpha_otps_collection.update_one(
        {"otp_code": code, "redemptions.email": normalized_email},
        {
            "$inc": {"use_count": -1},
            "$pull": {"redemptions": {"email": normalized_email}},
            "$set": {"used": False},
        },
    )
    if result.modified_count != 1:
        return False
    alpha_otps_collection.update_one(
        {"otp_code": code, "used_by_email": normalized_email},
        {"$set": {"used_by_email": None, "used_at": None}},
    )
    return True


def validate_otp(otp_code: str) -> Tuple[bool, Optional[str]]:
    """Read-only legacy wrapper around inspect_code."""
    if not otp_code:
        return False, "Alpha access code is required"
    ok, reason = inspect_code(otp_code)
    if ok:
        return True, None
    if reason == "exhausted":
        return False, "All spots on this code are claimed."
    if reason == "inactive":
        return False, "Invalid alpha access code"
    if len(normalize_otp_code(otp_code)) < MIN_OTP_LENGTH:
        return False, "Invalid alpha access code format"
    return False, "Invalid alpha access code"


def consume_otp(otp_code: str, email: str) -> Tuple[bool, Optional[str]]:
    """Legacy one-shot consume. Prefer reserve_code for signup."""
    ok, reason = reserve_code(otp_code, email)
    if ok:
        return True, None
    if reason == "exhausted":
        return False, "Alpha access code is no longer available"
    return False, "Invalid alpha access code"


def get_otp_status(otp_code: str) -> Optional[dict]:
    if not otp_code:
        return None
    code = normalize_otp_code(otp_code)
    otp_doc = alpha_otps_collection.find_one({"otp_code": code})
    if not otp_doc:
        return None
    return {
        "otp_code": otp_doc["otp_code"],
        "used": otp_doc.get("used", False),
        "used_by_email": otp_doc.get("used_by_email"),
        "used_at": otp_doc.get("used_at"),
        "created_at": otp_doc.get("created_at"),
        "max_uses": _max_uses(otp_doc),
        "use_count": _use_count(otp_doc),
        "active": otp_doc.get("active") is not False,
    }


def get_available_otp_count() -> int:
    return alpha_otps_collection.count_documents({"used": False})


def get_otp_stats() -> dict:
    total = alpha_otps_collection.count_documents({})
    used = alpha_otps_collection.count_documents({"used": True})
    available = alpha_otps_collection.count_documents({"used": False})
    return {
        "total": total,
        "used": used,
        "available": available,
        "usage_rate": (used / total * 100) if total > 0 else 0,
    }
