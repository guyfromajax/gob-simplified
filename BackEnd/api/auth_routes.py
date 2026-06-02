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
from typing import Literal, Optional

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
from BackEnd.db import (
    users_collection,
    password_reset_tokens_collection,
    access_code_requests_collection,
    franchises_collection,
    franchise_team_data_collection,
    teams_collection,
)
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
from BackEnd.utils.user_tracking import default_user_tracking, compute_lead_archetype
from BackEnd.utils.alpha_access_email import send_alpha_welcome_email, send_alpha_waitlist_email
from BackEnd.utils.alpha_otp_service import (
    claim_otp_for_email,
    count_available_otps,
    find_otp_for_email,
    release_otp_claim,
)

RESET_LINK_BASE_URL = os.getenv("RESET_LINK_BASE_URL", "https://www.geekedoutbasketball.com")
RESET_TOKEN_EXPIRY_HOURS = 1
ACCESS_CODE_RATE_LIMIT_PER_HOUR = int(os.getenv("ALPHA_ACCESS_CODE_RATE_LIMIT_PER_HOUR", "3"))


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


TutorialStep = Literal[
    "persona_intro",
    "team_select",
    "username",
    "situation",
    "set_lineup",
    "in_game",
    "complete",
]


class TutorialState(BaseModel):
    """Server-side state for the FTE v2 tutorial-game funnel."""
    step: TutorialStep
    team_pick: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# Index map for forward-only step validation. Higher = later in the funnel.
# persona_intro was prepended in the FTE v2 onboarding redesign (Sammy persona
# intro screen). Grandfathered users already past team_select don't need
# migration — the routing logic treats their existing step as still valid.
_TUTORIAL_STEP_ORDER = {
    "persona_intro": 0,
    "team_select": 1,
    "username": 2,
    "situation": 3,
    "set_lineup": 4,
    "in_game": 5,
    "complete": 6,
}


class TutorialAdvanceRequest(BaseModel):
    """Advance the tutorial to a new step. Forward-only on the server."""
    step: TutorialStep
    team_pick: Optional[str] = None


class UserResponse(BaseModel):
    """User info response."""
    user_id: str
    email: str
    role: str
    username: Optional[str] = None
    created_at: Optional[str] = None
    fte: Optional[bool] = None  # Legacy first-time experience flag (preserved during FTE v2 migration)
    fte_v2_complete: Optional[bool] = None  # FTE v2 — True once debut publish succeeds
    tutorial_state: Optional[TutorialState] = None
    account_settings: Optional[dict] = None
    record: Optional[dict] = None  # Career record (wins/losses/total_games/win_rate/discount_*)
    archetypes: Optional[dict] = None  # 18 coaching-archetype counters + total
    lead_archetype: Optional[str] = None  # denormalized top archetype key for the badge ("" if none)
    archetype_reveal_seen: Optional[bool] = None  # gates the one-time first-archetype reveal
    subscription: Optional[str] = None  # e.g. "alpha" — drives the account-page Status field
    geek_points: Optional[int] = None  # total geek points
    geek_points_by_team: Optional[dict] = None  # canonical team_id -> int (lazy; {} when none)
    championships_total: Optional[dict] = None  # { conf_rs, conf_t, region, national } -> int counts


class AuthConfigResponse(BaseModel):
    """Auth configuration response."""
    is_alpha: bool
    otp_required: bool


class LeaderboardEntry(BaseModel):
    """Leaderboard entry."""
    rank: int
    username: str
    geek_points: int
    is_current_user: bool = False
    lead_archetype: str = ""  # coach's badge key ("" = no badge)


class LeaderboardRankEntry(BaseModel):
    """Franchise rank leaderboard entry."""
    rank: int
    username: str
    team_name: str
    team_primary_color: str = "#27408E"
    natl_rank: int
    is_current_user: bool = False
    lead_archetype: str = ""  # coach's badge key ("" = no badge)


class LeaderboardResponse(BaseModel):
    """Leaderboard response."""
    top: list[LeaderboardEntry]
    current_user: Optional[LeaderboardEntry] = None
    rank_top: list[LeaderboardRankEntry] = []


class ResetRequest(BaseModel):
    """Password reset request - send reset link to email."""
    email: EmailStr


class RequestAccessCodeRequest(BaseModel):
    """Request an alpha access code (signup page). Stores request for admin to process manually."""
    email: EmailStr


class UpdateAccountSettingsRequest(BaseModel):
    """Update supported account settings for the authenticated user."""
    display_color: str

    @field_validator('display_color')
    @classmethod
    def validate_display_color(cls, v):
        normalized = str(v or "").strip().lower()
        if normalized not in {"default", "team_colors"}:
            raise ValueError("display_color must be 'default' or 'team_colors'")
        return normalized


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


def _redact_email(email: str) -> str:
    """Redact email for logging: a***@domain.com"""
    if "@" in email:
        local, domain = email.split("@", 1)
        return f"{local[:1]}***@{domain}" if len(local) > 1 else f"***@{domain}"
    return "***"


def _access_code_rate_limit_exceeded(email: str, now: datetime) -> bool:
    window_start = now - timedelta(hours=1)
    recent = access_code_requests_collection.count_documents(
        {
            "email": email,
            "created_at": {"$gte": window_start},
        }
    )
    return recent >= ACCESS_CODE_RATE_LIMIT_PER_HOUR


def _trigger_password_reset_for_email(email: str) -> None:
    user = get_user_by_email(email)
    if not user:
        return
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)
    password_reset_tokens_collection.insert_one({
        "token": token,
        "user_id": user["_id"],
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc),
    })
    reset_link = f"{RESET_LINK_BASE_URL.rstrip('/')}/reset-password.html?token={token}"
    send_password_reset_email(email, reset_link)


def _record_access_code_request(
    *,
    email: str,
    now: datetime,
    status: str,
    otp_code: str | None = None,
    sent_at: datetime | None = None,
) -> None:
    doc = {
        "email": email,
        "created_at": now,
        "status": status,
    }
    if otp_code is not None:
        doc["otp_code"] = otp_code
    if sent_at is not None:
        doc["sent_at"] = sent_at
    access_code_requests_collection.insert_one(doc)


@router.post("/request-access-code")
@_auth_rate_limit
async def request_access_code(request: Request, body: RequestAccessCodeRequest):
    """
    Request an alpha access code.

    Sends a welcome email with OTP when capacity exists, a waitlist email when not,
    or triggers password reset when the email is already registered.
    """
    email = body.email.lower().strip()
    now = datetime.now(timezone.utc)

    if _access_code_rate_limit_exceeded(email, now):
        raise HTTPException(
            status_code=429,
            detail="Too many access code requests. Please try again later.",
        )

    if get_user_by_email(email):
        logger.info("Access code request for registered user %s — sending reset", _redact_email(email))
        _trigger_password_reset_for_email(email)
        _record_access_code_request(email=email, now=now, status="skipped")
        return JSONResponse(
            content={
                "message": "If an account exists with that email, you will receive a reset link shortly."
            },
            status_code=200,
        )

    existing_otp = find_otp_for_email(email)
    if existing_otp:
        otp_code = existing_otp["otp_code"]
        sent = send_alpha_welcome_email(email, otp_code)
        status = "sent" if sent else "failed"
        _record_access_code_request(
            email=email,
            now=now,
            status=status,
            otp_code=otp_code,
            sent_at=now if sent else None,
        )
        if not sent:
            logger.warning("Failed to resend alpha welcome email to %s", _redact_email(email))
        return JSONResponse(
            content={"message": "Request received. We'll send your access code shortly."},
            status_code=200,
        )

    if count_available_otps() == 0:
        sent = send_alpha_waitlist_email(email)
        status = "waitlisted" if sent else "failed"
        _record_access_code_request(email=email, now=now, status=status)
        if not sent:
            logger.warning("Failed to send waitlist email to %s", _redact_email(email))
        return JSONResponse(
            content={"message": "Request received. We'll send your access code shortly."},
            status_code=200,
        )

    otp_code = claim_otp_for_email(email)
    if not otp_code:
        sent = send_alpha_waitlist_email(email)
        status = "waitlisted" if sent else "failed"
        _record_access_code_request(email=email, now=now, status=status)
        return JSONResponse(
            content={"message": "Request received. We'll send your access code shortly."},
            status_code=200,
        )

    sent = send_alpha_welcome_email(email, otp_code)
    if not sent:
        release_otp_claim(otp_code)
        _record_access_code_request(email=email, now=now, status="failed", otp_code=otp_code)
        logger.warning("Failed to send alpha welcome email to %s", _redact_email(email))
        return JSONResponse(
            content={"message": "Request received. We'll send your access code shortly."},
            status_code=200,
        )

    _record_access_code_request(
        email=email,
        now=now,
        status="sent",
        otp_code=otp_code,
        sent_at=now,
    )
    logger.info("Access code email sent to %s", _redact_email(email))
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
        "account_settings": {
            "display_color": "default"
        },
        "geek_points": 0,
        "fte": True,
        "fte_v2_complete": False,
        "tutorial_state": {
            "step": "persona_intro",
            "team_pick": None,
            "started_at": now,
            "completed_at": None,
        },
        # Career tracking blocks (record + 18 archetypes). Same shape the
        # backfill applies to existing users — single source of truth in
        # BackEnd/utils/user_tracking.py.
        **default_user_tracking(),
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
            "username": None,
            "fte": True,
            "fte_v2_complete": False,
            "tutorial_state": {
                "step": "persona_intro",
                "team_pick": None,
                "started_at": now.isoformat(),
                "completed_at": None,
            },
            "account_settings": {
                "display_color": "default"
            }
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
            "username": user.get("username"),
            "account_settings": user.get("account_settings") or {"display_color": "default"}
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


@router.patch("/account-settings")
async def update_account_settings(
    request: UpdateAccountSettingsRequest,
    user: dict = Depends(get_current_user),
):
    """
    Update account settings for the authenticated user.
    Account settings are nested to allow future expansion without flattening the user document.
    """
    display_color = request.display_color
    users_collection.update_one(
        {"_id": ObjectId(user["user_id"])},
        {
            "$set": {
                "account_settings.display_color": display_color,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    return {
        "account_settings": {
            "display_color": display_color
        },
        "message": "Account settings updated successfully"
    }


@router.patch("/archetype-reveal-seen")
async def mark_archetype_reveal_seen(user: dict = Depends(get_current_user)):
    """Mark the one-time first-archetype reveal modal as seen for this account.

    Idempotent; called by the frontend when the reveal is shown so it never
    appears again on any device/session.
    """
    users_collection.update_one(
        {"_id": ObjectId(user["user_id"])},
        {"$set": {"archetype_reveal_seen": True, "updated_at": datetime.now(timezone.utc)}}
    )
    return {"archetype_reveal_seen": True, "message": "Archetype reveal marked seen"}


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
    # FTE: True = show first-time experience; False = already completed (default True if missing)
    fte = db_user.get("fte", True) if db_user else True
    # FTE v2: returned as None for users predating the schema; populated post-migration.
    fte_v2_complete = db_user.get("fte_v2_complete") if db_user else None
    raw_tutorial_state = db_user.get("tutorial_state") if db_user else None
    tutorial_state = None
    if isinstance(raw_tutorial_state, dict) and raw_tutorial_state.get("step"):
        def _iso(v):
            if v is None:
                return None
            return v.isoformat() if hasattr(v, "isoformat") else str(v)
        tutorial_state = TutorialState(
            step=raw_tutorial_state["step"],
            team_pick=raw_tutorial_state.get("team_pick"),
            started_at=_iso(raw_tutorial_state.get("started_at")),
            completed_at=_iso(raw_tutorial_state.get("completed_at")),
        )
    account_settings = (db_user.get("account_settings") if db_user else None) or {"display_color": "default"}
    # Career tracking (read-only here). Fall back to canonical zeroed defaults so
    # the response is always well-shaped, even for a user not yet backfilled.
    tracking_defaults = default_user_tracking()
    record = (db_user.get("record") if db_user else None) or tracking_defaults["record"]
    archetypes = (db_user.get("archetypes") if db_user else None) or tracking_defaults["archetypes"]
    # lead_archetype is denormalized server-side; fall back to deriving from counts
    # for older docs that predate the field (UI also handles its absence).
    lead_archetype = (db_user.get("lead_archetype") if db_user else None)
    if lead_archetype is None:
        lead_archetype = compute_lead_archetype(archetypes)
    archetype_reveal_seen = bool(db_user.get("archetype_reveal_seen")) if db_user else False
    # Account-page fields (read-only). championships_total is lazily created by the
    # award logic, so default the four kinds to 0 for coaches with no titles.
    subscription = (db_user.get("subscription") if db_user else None) or "alpha"
    geek_points = int(db_user.get("geek_points", 0) or 0) if db_user else 0
    geek_points_by_team = (db_user.get("geek_points_by_team") if db_user else None) or {}
    raw_champs = (db_user.get("championships_total") if db_user else None) or {}
    championships_total = {k: int(raw_champs.get(k, 0) or 0) for k in ("conf_rs", "conf_t", "region", "national")}

    return UserResponse(
        user_id=user["user_id"],
        email=user["email"],
        role=role,
        username=username,
        created_at=created_at,
        fte=fte,
        fte_v2_complete=fte_v2_complete,
        tutorial_state=tutorial_state,
        account_settings=account_settings,
        record=record,
        archetypes=archetypes,
        lead_archetype=lead_archetype,
        archetype_reveal_seen=archetype_reveal_seen,
        subscription=subscription,
        geek_points=geek_points,
        geek_points_by_team=geek_points_by_team,
        championships_total=championships_total
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(user: dict = Depends(get_current_user)):
    """
    Return the alpha leaderboard ranked by geek_points.
    """
    current_user_id = str(user.get("user_id", "")).strip()
    docs = list(users_collection.find(
        {},
        {
            "_id": 1,
            "username": 1,
            "email": 1,
            "geek_points": 1,
            "lead_archetype": 1,
        }
    ))

    entries = []
    for doc in docs:
        username = str(doc.get("username") or "").strip()
        if not username:
            email = str(doc.get("email") or "").strip()
            username = email.split("@", 1)[0].strip() if email else "Coach"
        geek_points = doc.get("geek_points", 0)
        try:
            geek_points = int(geek_points)
        except Exception:
            geek_points = 0

        entries.append({
            "_id": str(doc.get("_id", "")),
            "username": username,
            "geek_points": geek_points,
            "lead_archetype": str(doc.get("lead_archetype") or ""),
        })

    entries.sort(key=lambda entry: (-entry["geek_points"], entry["username"].lower()))

    ranked_entries = []
    current_user_entry = None
    for index, entry in enumerate(entries, start=1):
        ranked = LeaderboardEntry(
            rank=index,
            username=entry["username"],
            geek_points=entry["geek_points"],
            is_current_user=(entry["_id"] == current_user_id),
            lead_archetype=entry["lead_archetype"],
        )
        ranked_entries.append(ranked)
        if ranked.is_current_user:
            current_user_entry = ranked

    franchise_docs = list(franchises_collection.find(
        {},
        {
            "_id": 1,
            "user_id": 1,
            "user_team_id": 1,
            "user_team_object_id": 1,
        }
    ))
    users_by_id = {entry["_id"]: entry for entry in entries}
    latest_franchise_by_user_id = {}
    for franchise_doc in franchise_docs:
        user_id = str(franchise_doc.get("user_id") or "").strip()
        if not user_id:
            continue
        existing = latest_franchise_by_user_id.get(user_id)
        if existing is None or franchise_doc["_id"] > existing["_id"]:
            latest_franchise_by_user_id[user_id] = franchise_doc
    team_ids = []
    for doc in latest_franchise_by_user_id.values():
        team_oid = str(doc.get("user_team_object_id") or "").strip()
        if team_oid:
            try:
                team_ids.append(ObjectId(team_oid))
            except Exception:
                pass
    teams_by_id = {}
    if team_ids:
        teams_by_id = {
            str(doc["_id"]): doc
            for doc in teams_collection.find(
                {"_id": {"$in": team_ids}},
                {"name": 1, "primary_color": 1},
            )
        }

    rank_entries_raw = []
    for user_id, franchise_doc in latest_franchise_by_user_id.items():
        if not user_id:
            continue
        user_entry = users_by_id.get(user_id)
        if not user_entry:
            continue

        team_object_id = str(franchise_doc.get("user_team_object_id") or "").strip()
        team_name = str(franchise_doc.get("user_team_id") or "").strip()
        if not team_object_id or not team_name:
            continue

        try:
            ftd_doc = franchise_team_data_collection.find_one(
                {
                    "franchise_id": franchise_doc["_id"],
                    "team_id": ObjectId(team_object_id),
                },
                {"natl_rank": 1},
            )
        except Exception:
            continue
        if not ftd_doc:
            continue

        natl_rank_raw = ftd_doc.get("natl_rank")
        try:
            natl_rank = int(natl_rank_raw)
        except Exception:
            continue
        if natl_rank <= 0:
            continue

        team_doc = teams_by_id.get(team_object_id) or {}
        team_primary_color = str(team_doc.get("primary_color") or "#27408E")

        rank_entries_raw.append({
            "_id": user_entry["_id"],
            "username": user_entry["username"],
            "team_name": team_name,
            "team_primary_color": team_primary_color,
            "natl_rank": natl_rank,
            "lead_archetype": user_entry.get("lead_archetype", ""),
        })

    rank_entries_raw.sort(key=lambda entry: (entry["natl_rank"], entry["username"].lower()))
    ranked_rank_entries = [
        LeaderboardRankEntry(
            rank=index,
            username=entry["username"],
            team_name=entry["team_name"],
            team_primary_color=entry["team_primary_color"],
            natl_rank=entry["natl_rank"],
            is_current_user=(entry["_id"] == current_user_id),
            lead_archetype=entry.get("lead_archetype", ""),
        )
        for index, entry in enumerate(rank_entries_raw, start=1)
    ]

    return LeaderboardResponse(
        top=ranked_entries[:10],
        current_user=(None if current_user_entry and current_user_entry.rank <= 10 else current_user_entry),
        rank_top=ranked_rank_entries[:5],
    )


@router.post("/fte-complete")
async def fte_complete(user: dict = Depends(get_current_user)):
    """
    Mark the first-time experience as completed for the current user.
    Sets fte to False so the FTE pop-up is not shown again.
    """
    try:
        users_collection.update_one(
            {"_id": ObjectId(user["user_id"])},
            {"$set": {"fte": False, "updated_at": datetime.now(timezone.utc)}}
        )
    except Exception as e:
        logger.warning("[FTE] fte-complete update failed for user_id=%s: %s", user["user_id"], e)
        raise HTTPException(status_code=500, detail="Failed to update FTE status")
    return {"message": "FTE completed", "fte": False}


@router.post("/tutorial-advance")
async def tutorial_advance(
    body: TutorialAdvanceRequest,
    user: dict = Depends(get_current_user),
):
    """
    Advance the user's tutorial_state to a new step. Server enforces
    forward-only transitions: a target step earlier than the current step
    is rejected with 400. Same-step posts are idempotent.

    team_pick (optional) is persisted if provided.
    """
    target_step = body.step
    target_idx = _TUTORIAL_STEP_ORDER[target_step]

    db_user = users_collection.find_one({"_id": ObjectId(user["user_id"])})
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    current_state = db_user.get("tutorial_state") or {}
    current_step = current_state.get("step", "team_select")
    current_idx = _TUTORIAL_STEP_ORDER.get(current_step, 0)

    if target_idx < current_idx:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot advance backward from '{current_step}' to '{target_step}'",
        )

    update = {
        "tutorial_state.step": target_step,
        "updated_at": datetime.now(timezone.utc),
    }
    if body.team_pick is not None:
        update["tutorial_state.team_pick"] = body.team_pick

    users_collection.update_one(
        {"_id": ObjectId(user["user_id"])},
        {"$set": update},
    )
    return {
        "step": target_step,
        "team_pick": body.team_pick if body.team_pick is not None else current_state.get("team_pick"),
    }


@router.post("/tutorial-complete")
async def tutorial_complete(user: dict = Depends(get_current_user)):
    """
    Mark the FTE v2 tutorial fully complete. Called by the tutorial post-game
    modal only after the debut publish succeeds. Sets fte_v2_complete=True and
    advances tutorial_state to 'complete'.
    """
    now = datetime.now(timezone.utc)
    try:
        users_collection.update_one(
            {"_id": ObjectId(user["user_id"])},
            {"$set": {
                "fte_v2_complete": True,
                "tutorial_state.step": "complete",
                "tutorial_state.completed_at": now,
                "updated_at": now,
            }},
        )
    except Exception as e:
        logger.warning("[FTE_V2] tutorial-complete update failed for user_id=%s: %s", user["user_id"], e)
        raise HTTPException(status_code=500, detail="Failed to mark tutorial complete")
    return {"fte_v2_complete": True, "step": "complete"}


@router.post("/logout")
async def logout():
    """
    Logout endpoint.
    
    JWT tokens are stateless, so logout is handled client-side by removing the token.
    This endpoint exists for API completeness and potential future server-side token invalidation.
    """
    return {"message": "Logged out successfully"}
