from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from BackEnd.db import alpha_feedback_collection, users_collection
from BackEnd.utils.auth import get_current_user
from BackEnd.utils.resend_sender import send_alpha_feedback_email

router = APIRouter()
logger = logging.getLogger(__name__)

# Per-IP throttle: 1 submission every 10 seconds (same as /api/feedback).
_last_submit_by_ip: dict[str, float] = {}
_submit_cooldown_seconds = 10

# Allowed rating labels per question. The 6 Section-01 questions share one set;
# the 2 Section-02 questions each have their own. Kept verbatim with the
# frontend's segmented-control labels (the corrected copy from the build prompt).
_OPINION_SET = {"Awful", "OK, but needs work", "Great"}
_RATING_ALLOWED: dict[str, set[str]] = {
    "live_gameplay": _OPINION_SET,
    "between_games": _OPINION_SET,
    "training": _OPINION_SET,
    "franchise_mode": _OPINION_SET,
    "high_school_setting": _OPINION_SET,
    "onboarding": _OPINION_SET,
    "game_length": {"Too Short", "Just Right", "Too Long"},
    "learning_curve": {"Too Easy", "Just Right", "Too Hard"},
}
_RATING_KEYS = tuple(_RATING_ALLOWED.keys())

_FAVORITE_MAX = 5000
_NOTE_MAX = 2000


class AlphaFeedbackRequest(BaseModel):
    # All 8 rating answers required; each value constrained to its allowed set below.
    ratings: Dict[str, str]
    # Only keys with a non-empty note; subset of the 8 rating keys. Never required.
    optional_notes: Dict[str, str] = Field(default_factory=dict)
    favorite: str = Field(..., max_length=_FAVORITE_MAX)
    least_favorite: str = Field(..., max_length=_FAVORITE_MAX)
    would_recommend: bool
    app_version: Optional[str] = Field(default=None, max_length=100)


@router.post("/api/alpha-feedback")
async def submit_alpha_feedback(
    request: Request,
    body: AlphaFeedbackRequest,
    user: dict = Depends(get_current_user),
):
    client_ip = (request.client.host if request.client else "unknown") or "unknown"
    now_mono = time.monotonic()
    last = _last_submit_by_ip.get(client_ip, 0.0)
    if now_mono - last < _submit_cooldown_seconds:
        raise HTTPException(status_code=429, detail="Please wait before submitting again.")
    _last_submit_by_ip[client_ip] = now_mono

    # --- Validate the 8 ratings: all present, each within its allowed set. ---
    missing = [k for k in _RATING_KEYS if k not in body.ratings]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing ratings: {', '.join(missing)}")
    for key in _RATING_KEYS:
        value = body.ratings.get(key)
        if value not in _RATING_ALLOWED[key]:
            raise HTTPException(status_code=422, detail=f"Invalid value for '{key}'.")
    ratings = {k: body.ratings[k] for k in _RATING_KEYS}  # canonical order, drop extras

    # --- Validate the two open-ended answers (required, non-empty trimmed). ---
    favorite = (body.favorite or "").strip()
    least_favorite = (body.least_favorite or "").strip()
    if not favorite or not least_favorite:
        raise HTTPException(status_code=422, detail="Both written answers are required.")

    # --- Optional notes: keep only non-empty, on known rating keys, capped. ---
    optional_notes: dict[str, str] = {}
    for key, note in (body.optional_notes or {}).items():
        if key not in _RATING_ALLOWED:
            continue
        trimmed = (note or "").strip()
        if trimmed:
            optional_notes[key] = trimmed[:_NOTE_MAX]

    user_id = str(user.get("user_id", "")).strip()
    user_label = user.get("username") or user.get("email") or ""

    context = {
        "user": user_label,
        "user_agent": request.headers.get("user-agent", ""),
        "ip": client_ip,
        "app_version": (body.app_version or "").strip(),
    }

    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "ratings": ratings,
        "optional_notes": optional_notes,
        "favorite": favorite[:_FAVORITE_MAX],
        "least_favorite": least_favorite[:_FAVORITE_MAX],
        "would_recommend": bool(body.would_recommend),
        "context": context,
        "updated_at": now,
    }

    # One canonical submission per user (upsert by user_id); preserve first created_at.
    try:
        alpha_feedback_collection.update_one(
            {"user_id": user_id},
            {"$set": payload, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    except Exception as exc:
        logger.warning("[ALPHA_FEEDBACK] Failed to persist survey: %s", exc)
        raise HTTPException(status_code=500, detail="Could not save feedback. Please try again.")

    # Flag the account so the prompt modal + nav-button rewire stop for good.
    try:
        users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"alpha_feedback_submitted": True, "updated_at": now}},
        )
    except Exception as exc:
        logger.warning("[ALPHA_FEEDBACK] Failed to set alpha_feedback_submitted: %s", exc)

    # Best-effort notification to the team inbox (never to the submitter).
    try:
        send_alpha_feedback_email(
            ratings=ratings,
            optional_notes=optional_notes,
            favorite=favorite,
            least_favorite=least_favorite,
            would_recommend=bool(body.would_recommend),
            context=context,
            user_label=user_label,
        )
    except Exception as exc:
        logger.warning("[ALPHA_FEEDBACK] Email send failed: %s", exc)

    return {"success": True, "alpha_feedback_submitted": True}
