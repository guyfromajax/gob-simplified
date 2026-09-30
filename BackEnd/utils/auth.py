"""
Authentication Utilities

Provides password hashing, JWT token management, and auth dependencies.

USAGE:
    from BackEnd.utils.auth import (
        hash_password,
        verify_password,
        create_access_token,
        get_current_user,
        get_current_user_optional
    )

    # Hash password for storage
    hashed = hash_password("user_password")
    
    # Verify password on login
    if verify_password("user_password", hashed):
        token = create_access_token({"sub": user_id, "email": email})
    
    # Protect endpoint (requires auth)
    @app.get("/protected")
    async def protected(user: dict = Depends(get_current_user)):
        return {"user_id": user["user_id"]}
    
    # Optional auth (returns None if not authenticated)
    @app.get("/public")
    async def public(user: dict = Depends(get_current_user_optional)):
        if user:
            return {"user_id": user["user_id"]}
        return {"message": "anonymous"}
"""

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from BackEnd.persistence import get_store
from BackEnd.utils.jwt_config import DEV_JWT_FALLBACK, resolve_jwt_secret
_store = get_store()
users_collection = _store.users_collection

logger = logging.getLogger(__name__)


# JWT Configuration. The app refuses to boot without a private secret outside local
# dev/test (BackEnd/api/_bootstrap.py -> jwt_config.resolve_jwt_secret). Signing and
# verification resolve it per call, so a script that imports this module for other
# helpers does not crash, but can never mint or accept a dev-secret token when hosted.
_dev_jwt_fallback = DEV_JWT_FALLBACK
# Legacy attribute (email_suppression's unsubscribe HMAC reads it); not used for JWTs.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", _dev_jwt_fallback)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

# Security scheme for FastAPI docs
security = HTTPBearer(auto_error=False)

# bcrypt only reads the first 72 bytes. New passwords over that are rejected (signup,
# reset); login truncates to 72 so accounts created before the limit still work.
BCRYPT_MAX_PASSWORD_BYTES = 72

# How long a user's token_version / role is trusted before re-reading the user doc.
USER_AUTH_CACHE_TTL_SECONDS = 60


def _jwt_secret() -> str:
    return resolve_jwt_secret()


def password_too_long(password: str) -> bool:
    return len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password (at most 72 UTF-8 bytes)
        
    Returns:
        Hashed password string
    """
    if password_too_long(password):
        raise ValueError(f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against its hash.

    Truncates to 72 bytes exactly as bcrypt < 5 did silently, so a legacy password
    longer than that still verifies.
    
    Args:
        password: Plain text password to verify
        hashed: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        pw = password.encode('utf-8')[:BCRYPT_MAX_PASSWORD_BYTES]
        return bcrypt.checkpw(pw, hashed.encode('utf-8'))
    except Exception:
        return False


_dummy_hash_lock = threading.Lock()
_dummy_password_hash: Optional[str] = None


def burn_password_check(password: str) -> None:
    """Spend one bcrypt verify on a fixed dummy hash (unknown-email login path), so
    an unknown email costs the same as a wrong password."""
    global _dummy_password_hash
    if _dummy_password_hash is None:
        with _dummy_hash_lock:
            if _dummy_password_hash is None:
                _dummy_password_hash = hash_password("dummy-password-not-a-user-1")
    verify_password(password, _dummy_password_hash)


# --- token revocation: user token_version + role, cached per process ----------

_auth_cache: dict[str, tuple[float, Optional[dict]]] = {}
_auth_cache_lock = threading.Lock()


def _load_user_auth_state(user_id: str) -> Optional[dict]:
    from bson import ObjectId
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    doc = users_collection.find_one({"_id": oid}, {"token_version": 1, "role": 1})
    if not doc:
        return None
    return {
        "token_version": int(doc.get("token_version", 0) or 0),
        "role": doc.get("role") or "user",
    }


def user_auth_state(user_id: str) -> Optional[dict]:
    """{token_version, role} for a user (None if no such user), cached ~60s."""
    now = time.monotonic()
    with _auth_cache_lock:
        hit = _auth_cache.get(user_id)
        if hit and hit[0] > now:
            return hit[1]
    state = _load_user_auth_state(user_id)
    with _auth_cache_lock:
        _auth_cache[user_id] = (now + USER_AUTH_CACHE_TTL_SECONDS, state)
    return state


def invalidate_user_auth_cache(user_id: Optional[str] = None) -> None:
    with _auth_cache_lock:
        if user_id is None:
            _auth_cache.clear()
        else:
            _auth_cache.pop(str(user_id), None)


def bump_token_version(user_id) -> None:
    """Invalidate every token issued to this user so far (logout / password reset)."""
    from bson import ObjectId
    oid = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
    users_collection.update_one({"_id": oid}, {"$inc": {"token_version": 1}})
    invalidate_user_auth_cache(str(oid))


def token_version_claim(user: Optional[dict]) -> int:
    """The `tv` claim for a token issued to this user doc (missing field = 0)."""
    return int((user or {}).get("token_version", 0) or 0)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Payload data (should include 'sub' for user_id)
        expires_delta: Optional custom expiration time
        
    Returns:
        JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, _jwt_secret(), algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload dict or None if invalid
    """
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    FastAPI dependency to get the current authenticated user.
    Raises 401 if not authenticated.
    
    Usage:
        @app.get("/protected")
        async def protected(user: dict = Depends(get_current_user)):
            return {"user_id": user["user_id"]}
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_token(credentials.credentials)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = _user_from_payload(payload)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _user_from_payload(payload: dict) -> Optional[dict]:
    """Current user for a decoded token, or None if the user is gone or the token
    was revoked (its `tv` claim, missing = 0, no longer matches token_version).

    Role comes from the user doc (cached), never from the token alone."""
    user_id = str(payload.get("sub") or "")
    if not user_id:
        return None
    try:
        state = user_auth_state(user_id)
    except Exception:
        logger.exception("[AUTH] user auth state lookup failed user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication temporarily unavailable",
        )
    if state is None:
        return None
    try:
        tv = int(payload.get("tv", 0) or 0)
    except (TypeError, ValueError):
        return None
    if tv != state["token_version"]:
        return None
    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "role": state["role"],
    }


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[dict]:
    """
    FastAPI dependency to optionally get the current user.
    Returns None if not authenticated (doesn't raise error).
    
    Usage:
        @app.get("/public")
        async def public(user: dict = Depends(get_current_user_optional)):
            if user:
                return {"user_id": user["user_id"]}
            return {"message": "anonymous"}
    """
    if not credentials:
        return None
    
    payload = decode_token(credentials.credentials)
    
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None

    return _user_from_payload(payload)


async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """
    FastAPI dependency that requires admin role.
    Raises 403 if user is not an admin. The role comes from get_current_user, which
    reads it from the user doc (cached), not from the token.
    
    Usage:
        @app.get("/admin-only")
        async def admin_only(user: dict = Depends(get_admin_user)):
            return {"admin": True}
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def _is_production() -> bool:
    """True when running in production (builder pages and APIs restricted to admin)."""
    env = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or os.getenv("RAILWAY_ENVIRONMENT") or "").lower()
    return env == "production"


async def require_admin_for_builder(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[dict]:
    """
    Step 12.4: In production, require admin role for builder endpoints.
    In staging/develop, allow (no auth required) for testing.
    """
    if not _is_production():
        return None
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    user = _user_from_payload(payload) if payload else None
    # Role from the user doc (cached), never from the token: a token claiming
    # admin for a non-admin user is refused.
    if not user or user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def get_user_by_email(email: str) -> Optional[dict]:
    """
    Get a user document by email.
    
    Args:
        email: User's email address
        
    Returns:
        User document or None if not found
    """
    return users_collection.find_one({"email": email.lower()})


def get_user_by_id(user_id: str) -> Optional[dict]:
    """
    Get a user document by ID.
    
    Args:
        user_id: User's ID (string)
        
    Returns:
        User document or None if not found
    """
    from bson import ObjectId
    try:
        return users_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None
