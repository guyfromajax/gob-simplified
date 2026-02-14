"""
Authentication API Routes

Provides signup, login, and user management endpoints.

ENDPOINTS:
    POST /api/auth/signup  - Create new account (OTP required when IS_ALPHA=true)
    POST /api/auth/login   - Login and get JWT token
    GET  /api/auth/me      - Get current user info (requires auth)
    GET  /api/auth/config  - Get auth configuration (IS_ALPHA status)
"""

import logging
import os
import re
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, field_validator
from bson import ObjectId

try:
    from BackEnd.utils.rate_limiter import limiter as _limiter, AUTH_RATE_LIMIT
    _auth_rate_limit = _limiter.limit(AUTH_RATE_LIMIT)
except Exception:
    def _auth_rate_limit(f):
        return f
from BackEnd.db import users_collection, password_reset_tokens_collection, access_code_requests_collection
from BackEnd.utils.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_user_by_email
)
from BackEnd.utils.otp_validator import (
    is_alpha_mode,
    validate_otp,
    consume_otp
)
from BackEnd.utils.email_sender import send_password_reset_email

RESET_LINK_BASE_URL = os.getenv("RESET_LINK_BASE_URL", "https://www.geekedoutbasketball.com")
RESET_TOKEN_EXPIRY_HOURS = 1


router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SignupRequest(BaseModel):
    """Signup request body."""
    email: EmailStr
    password: str
    otp_code: Optional[str] = None  # Required when IS_ALPHA=true
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        return _validate_password(v)


class LoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Authentication response with token."""
    token: str
    user: dict
    message: str


class UserResponse(BaseModel):
    """User info response."""
    user_id: str
    email: str
    role: str
    username: Optional[str] = None
    created_at: Optional[str] = None


class AuthConfigResponse(BaseModel):
    """Auth configuration response."""
    is_alpha: bool
    otp_required: bool


class ResetRequest(BaseModel):
    """Password reset request - send reset link to email."""
    email: EmailStr


class RequestAccessCodeRequest(BaseModel):
    """Request an alpha access code (signup page). Stores request for admin to process manually."""
    email: EmailStr


def _validate_password(v: str) -> str:
    """Shared password rules (signup and reset)."""
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v) > 128:
        raise ValueError("Password must be at most 128 characters")
    if not re.search(r"[A-Za-z]", v):
        raise ValueError("Password must contain at least one letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one number")
    return v


class ResetPasswordRequest(BaseModel):
    """Set new password using reset token."""
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        return _validate_password(v)


class SetUsernameRequest(BaseModel):
    """Set username request body."""
    username: str

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        v = v.strip()
        if " " in v:
            raise ValueError("Username cannot contain spaces")
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(v) > 24:
            raise ValueError("Username must be at most 24 characters")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        return v


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config():
    """
    Get authentication configuration.
    
    Returns whether the app is in alpha mode and if OTP is required for signup.
    Frontend uses this to conditionally show the OTP field.
    """
    alpha = is_alpha_mode()
    return AuthConfigResponse(
        is_alpha=alpha,
        otp_required=alpha
    )


@router.post("/request-access-code")
@_auth_rate_limit
async def request_access_code(request: Request, body: RequestAccessCodeRequest):
    """
    Record a request for an alpha access code.
    
    User enters email on signup page and clicks "Request Access Code".
    Request is stored in access_code_requests; admin checks the collection
    and sends codes manually. No email is sent (transactional email can be
    added later).
    """
    email = body.email.lower().strip()
    now = datetime.now(timezone.utc)
    doc = {
        "email": email,
        "created_at": now,
        "status": "pending",
    }
    access_code_requests_collection.insert_one(doc)
    logger.info("Access code request recorded for %s", email)
    return JSONResponse(
        content={"message": "Request received. We'll send your access code shortly."},
        status_code=200,
    )


@router.post("/signup")
@_auth_rate_limit
async def signup(request: Request, body: SignupRequest):
    """
    Create a new user account.
    
    When IS_ALPHA=true, a valid unused OTP code is required.
    The OTP is permanently linked to the user's email for tracking.
    
    Password requirements:
    - 8–128 characters
    - At least one letter
    - At least one number
    
    Rate limited: 10/minute per IP (prevents brute force OTP guessing).
    """
    email = body.email.lower().strip()
    
    # Check if alpha mode requires OTP
    if is_alpha_mode():
        if not body.otp_code:
            raise HTTPException(
                status_code=400,
                detail="Alpha access code is required for signup"
            )
        
        # Validate OTP
        is_valid, error = validate_otp(body.otp_code)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
    
    # Check if email already exists
    existing_user = get_user_by_email(email)
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists"
        )
    
    # Create user document
    now = datetime.now(timezone.utc)
    user_doc = {
        "email": email,
        "password_hash": hash_password(body.password),
        "role": "user",
        "subscription": "alpha",
        "geek_points": 0,
        "created_at": now,
        "updated_at": now,
        "version": 1  # Schema version for future migrations
    }
    
    # Insert user
    result = users_collection.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    # Consume OTP (mark as used) after successful user creation
    if is_alpha_mode() and body.otp_code:
        success, error = consume_otp(body.otp_code, email)
        if not success:
            # User was created but OTP consumption failed (race condition)
            # Log this but don't fail the signup
            print(f"⚠️ [AUTH] OTP consumption failed for {email}: {error}")
    
    # Create JWT token
    token = create_access_token({
        "sub": user_id,
        "email": email,
        "role": "user"
    })
    
    payload = AuthResponse(
        token=token,
        user={
            "user_id": user_id,
            "email": email,
            "role": "user",
            "username": None
        },
        message="Account created successfully"
    ).model_dump()
    return JSONResponse(content=payload, status_code=200)


@router.post("/login")
@_auth_rate_limit
async def login(request: Request, body: LoginRequest):
    """
    Login with email and password.
    
    Returns a JWT token for authenticated requests.
    
    Rate limited: 10/minute per IP (prevents brute force password guessing).
    """
    email = body.email.lower().strip()
    
    # Find user
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Create JWT token
    user_id = str(user["_id"])
    token = create_access_token({
        "sub": user_id,
        "email": email,
        "role": user.get("role", "user")
    })
    
    # Update last login timestamp
    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login_at": datetime.now(timezone.utc)}}
    )
    
    payload = AuthResponse(
        token=token,
        user={
            "user_id": user_id,
            "email": email,
            "role": user.get("role", "user"),
            "username": user.get("username")
        },
        message="Login successful"
    ).model_dump()
    return JSONResponse(content=payload, status_code=200)


@router.post("/set-username")
async def set_username(
    request: SetUsernameRequest,
    user: dict = Depends(get_current_user),
):
    """
    Set the authenticated user's username.
    Usernames are displayed case-sensitive, but uniqueness is case-insensitive.
    If CoachJamie is taken, coachjamie, COACHJAMIE, etc. are all unavailable.
    """
    username = request.username.strip()
    username_lower = username.lower()

    # Check uniqueness (case-insensitive)
    existing = users_collection.find_one({"username_lower": username_lower})
    if existing and str(existing["_id"]) != user["user_id"]:
        raise HTTPException(
            status_code=400,
            detail="This username is already taken"
        )

    # User updating their own username - allow
    users_collection.update_one(
        {"_id": ObjectId(user["user_id"])},
        {"$set": {"username": username, "username_lower": username_lower, "updated_at": datetime.now(timezone.utc)}}
    )

    return {"username": username, "message": "Username set successfully"}


def _redact_email(email: str) -> str:
    """Redact email for logging: a***@domain.com"""
    if "@" in email:
        local, domain = email.split("@", 1)
        return f"{local[:1]}***@{domain}" if len(local) > 1 else f"***@{domain}"
    return "***"


@router.post("/reset-request")
@_auth_rate_limit
async def password_reset_request(request: Request, body: ResetRequest):
    """
    Request a password reset email.

    If the email is registered, a reset link is sent (when email is configured).
    Always returns 200 with a generic message to avoid leaking whether the email exists.
    """
    email = body.email.lower().strip()
    # Use WARNING so logs appear even when app log level is WARNING
    logger.warning("[RESET] reset-request received for %s", _redact_email(email))
    user = get_user_by_email(email)
    if user:
        logger.warning("[RESET] user found, creating token and sending email")
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)
        password_reset_tokens_collection.insert_one({
            "token": token,
            "user_id": user["_id"],
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        })
        reset_link = f"{RESET_LINK_BASE_URL.rstrip('/')}/reset-password.html?token={token}"
        sent = send_password_reset_email(email, reset_link)
        logger.warning("[RESET] send_password_reset_email returned %s", sent)
    else:
        logger.warning("[RESET] user not found (no email sent)")
    return JSONResponse(
        content={"message": "If an account exists with that email, you will receive a reset link shortly."},
        status_code=200,
    )


@router.post("/reset-password")
@_auth_rate_limit
async def password_reset_confirm(request: Request, body: ResetPasswordRequest):
    """
    Set a new password using the token from the reset email.

    Token is invalidated after use. Returns 400 if token is invalid or expired.
    """
    logger.warning("[RESET] reset-password received (token length=%s)", len(body.token) if body.token else 0)
    doc = password_reset_tokens_collection.find_one({"token": body.token})
    if not doc:
        logger.warning("[RESET] reset-password: token not found or already used")
        raise HTTPException(status_code=400, detail="Invalid or expired reset link. Please request a new one.")
    expires_at = doc.get("expires_at")
    if expires_at is None:
        logger.warning("[RESET] reset-password: token missing expires_at")
        raise HTTPException(status_code=400, detail="Invalid or expired reset link. Please request a new one.")
    now_utc = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now_utc:
        password_reset_tokens_collection.delete_one({"_id": doc["_id"]})
        logger.warning("[RESET] reset-password: token expired")
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")
    user_id = doc["user_id"]
    if not isinstance(user_id, ObjectId):
        user_id = ObjectId(user_id)
    users_collection.update_one(
        {"_id": user_id},
        {"$set": {"password_hash": hash_password(body.new_password), "updated_at": datetime.now(timezone.utc)}}
    )
    password_reset_tokens_collection.delete_many({"user_id": user_id})
    logger.warning("[RESET] reset-password: password updated for user_id=%s", user_id)
    return JSONResponse(
        content={"message": "Password updated. You can now log in with your new password."},
        status_code=200,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """
    Get the current authenticated user's info.
    
    Requires a valid JWT token in the Authorization header.
    """
    # Optionally fetch fresh user data from DB
    db_user = None
    try:
        db_user = users_collection.find_one({"_id": ObjectId(user["user_id"])})
    except Exception:
        pass
    
    created_at = None
    if db_user and db_user.get("created_at"):
        created_at = db_user["created_at"].isoformat() if hasattr(db_user["created_at"], 'isoformat') else str(db_user["created_at"])

    username = db_user.get("username") if db_user else None
    # Use role from DB when available so admin status is live (no re-login needed)
    role = db_user.get("role", user.get("role", "user")) if db_user else user.get("role", "user")

    return UserResponse(
        user_id=user["user_id"],
        email=user["email"],
        role=role,
        username=username,
        created_at=created_at
    )


@router.post("/logout")
async def logout():
    """
    Logout endpoint.
    
    JWT tokens are stateless, so logout is handled client-side by removing the token.
    This endpoint exists for API completeness and potential future server-side token invalidation.
    """
    return {"message": "Logged out successfully"}
