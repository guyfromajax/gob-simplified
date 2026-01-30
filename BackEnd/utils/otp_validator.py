"""
OTP Validation Utility

Provides functions for validating and consuming alpha OTP codes.
Used by the authentication system during signup when IS_ALPHA=true.

USAGE:
    from BackEnd.utils.otp_validator import validate_otp, consume_otp, is_alpha_mode

    # Check if alpha mode is enabled
    if is_alpha_mode():
        # Validate OTP before signup
        is_valid, error = validate_otp(otp_code)
        if not is_valid:
            return {"error": error}
        
        # After successful user creation, consume the OTP
        consume_otp(otp_code, user_email)
"""

import os
from datetime import datetime, timezone
from typing import Tuple, Optional

from BackEnd.db import alpha_otps_collection


def is_alpha_mode() -> bool:
    """
    Check if the application is running in alpha mode.
    
    Returns:
        True if IS_ALPHA environment variable is set to 'true' (case-insensitive)
    """
    return os.getenv("IS_ALPHA", "false").lower() == "true"


def validate_otp(otp_code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate an OTP code without consuming it.
    
    This should be called BEFORE creating the user account to ensure the OTP
    is valid. If valid, call consume_otp() AFTER the user is created.
    
    Args:
        otp_code: The OTP code to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if the OTP is valid and unused
        - (False, "error message") if invalid
    """
    if not otp_code:
        return False, "Alpha access code is required"
    
    # Normalize: strip whitespace, uppercase
    otp_code = otp_code.strip().upper()
    
    if len(otp_code) < 6:
        return False, "Invalid alpha access code format"
    
    # Look up OTP in database
    otp_doc = alpha_otps_collection.find_one({"otp_code": otp_code})
    
    if not otp_doc:
        return False, "Invalid alpha access code"
    
    if otp_doc.get("used"):
        # Check if it was used by this same code (duplicate signup attempt)
        used_by = otp_doc.get("used_by_email")
        if used_by:
            return False, f"This alpha access code has already been used"
        return False, "This alpha access code has already been used"
    
    return True, None


def consume_otp(otp_code: str, email: str) -> Tuple[bool, Optional[str]]:
    """
    Mark an OTP as used by a specific email.
    
    This should be called AFTER successfully creating the user account.
    The OTP is permanently linked to this email for tracking purposes.
    
    Args:
        otp_code: The OTP code to consume
        email: The email address of the user who used this OTP
        
    Returns:
        Tuple of (success, error_message)
        - (True, None) if successfully consumed
        - (False, "error message") if failed
    """
    if not otp_code or not email:
        return False, "OTP code and email are required"
    
    # Normalize
    otp_code = otp_code.strip().upper()
    email = email.strip().lower()
    
    now = datetime.now(timezone.utc)
    
    # Atomically update OTP - only if it's still unused
    result = alpha_otps_collection.update_one(
        {
            "otp_code": otp_code,
            "used": False
        },
        {
            "$set": {
                "used": True,
                "used_by_email": email,
                "used_at": now
            }
        }
    )
    
    if result.modified_count == 0:
        # OTP was already used (race condition) or doesn't exist
        return False, "Alpha access code is no longer available"
    
    return True, None


def get_otp_status(otp_code: str) -> Optional[dict]:
    """
    Get the status of an OTP code.
    
    Args:
        otp_code: The OTP code to check
        
    Returns:
        Dict with OTP status or None if not found
    """
    if not otp_code:
        return None
    
    otp_code = otp_code.strip().upper()
    otp_doc = alpha_otps_collection.find_one({"otp_code": otp_code})
    
    if not otp_doc:
        return None
    
    return {
        "otp_code": otp_doc["otp_code"],
        "used": otp_doc.get("used", False),
        "used_by_email": otp_doc.get("used_by_email"),
        "used_at": otp_doc.get("used_at"),
        "created_at": otp_doc.get("created_at")
    }


def get_available_otp_count() -> int:
    """
    Get the number of unused OTPs remaining.
    
    Returns:
        Count of unused OTPs
    """
    return alpha_otps_collection.count_documents({"used": False})


def get_otp_stats() -> dict:
    """
    Get overall OTP statistics.
    
    Returns:
        Dict with total, used, and available counts
    """
    total = alpha_otps_collection.count_documents({})
    used = alpha_otps_collection.count_documents({"used": True})
    available = alpha_otps_collection.count_documents({"used": False})
    
    return {
        "total": total,
        "used": used,
        "available": available,
        "usage_rate": (used / total * 100) if total > 0 else 0
    }
