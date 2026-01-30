"""
Authentication API Routes

Provides signup, login, and user management endpoints.

ENDPOINTS:
    POST /api/auth/signup  - Create new account (OTP required when IS_ALPHA=true)
    POST /api/auth/login   - Login and get JWT token
    GET  /api/auth/me      - Get current user info (requires auth)
    GET  /api/auth/config  - Get auth configuration (IS_ALPHA status)
"""

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, field_validator
from bson import ObjectId

from BackEnd.db import users_collection
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


router = APIRouter(prefix="/api/auth", tags=["auth"])


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
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('Password must contain at least one letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v


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
    created_at: Optional[str] = None


class AuthConfigResponse(BaseModel):
    """Auth configuration response."""
    is_alpha: bool
    otp_required: bool


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


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    """
    Create a new user account.
    
    When IS_ALPHA=true, a valid unused OTP code is required.
    The OTP is permanently linked to the user's email for tracking.
    
    Password requirements:
    - At least 8 characters
    - At least one letter
    - At least one number
    """
    email = request.email.lower().strip()
    
    # Check if alpha mode requires OTP
    if is_alpha_mode():
        if not request.otp_code:
            raise HTTPException(
                status_code=400,
                detail="Alpha access code is required for signup"
            )
        
        # Validate OTP
        is_valid, error = validate_otp(request.otp_code)
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
        "password_hash": hash_password(request.password),
        "role": "user",
        "created_at": now,
        "updated_at": now,
        "version": 1  # Schema version for future migrations
    }
    
    # Insert user
    result = users_collection.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    # Consume OTP (mark as used) after successful user creation
    if is_alpha_mode() and request.otp_code:
        success, error = consume_otp(request.otp_code, email)
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
    
    return AuthResponse(
        token=token,
        user={
            "user_id": user_id,
            "email": email,
            "role": "user"
        },
        message="Account created successfully"
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """
    Login with email and password.
    
    Returns a JWT token for authenticated requests.
    """
    email = request.email.lower().strip()
    
    # Find user
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(request.password, user.get("password_hash", "")):
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
    
    return AuthResponse(
        token=token,
        user={
            "user_id": user_id,
            "email": email,
            "role": user.get("role", "user")
        },
        message="Login successful"
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
    
    return UserResponse(
        user_id=user["user_id"],
        email=user["email"],
        role=user.get("role", "user"),
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
