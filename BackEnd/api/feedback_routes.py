from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from BackEnd.db import db
from BackEnd.utils.resend_sender import send_feedback_email

router = APIRouter()
logger = logging.getLogger(__name__)

feedback_collection = db["feedback_submissions"]

# Basic per-IP throttle: 1 submission every 10 seconds.
_last_feedback_by_ip: dict[str, float] = {}
_feedback_cooldown_seconds = 10


class FeedbackRequest(BaseModel):
    category: str = Field(default="general", min_length=1, max_length=40)
    message: str = Field(..., min_length=5, max_length=5000)
    reporter_email: Optional[str] = Field(default=None, max_length=254)
    page_url: Optional[str] = Field(default=None, max_length=1000)
    page_path: Optional[str] = Field(default=None, max_length=500)
    mode: Optional[str] = Field(default=None, max_length=50)
    user_label: Optional[str] = Field(default=None, max_length=200)


@router.post("/api/feedback")
def submit_feedback(request: Request, body: FeedbackRequest):
    client_ip = (request.client.host if request.client else "unknown") or "unknown"
    now = time.monotonic()
    last = _last_feedback_by_ip.get(client_ip, 0.0)
    if now - last < _feedback_cooldown_seconds:
        raise HTTPException(status_code=429, detail="Please wait before submitting more feedback.")
    _last_feedback_by_ip[client_ip] = now

    normalized_category = (body.category or "general").strip().lower()
    allowed_categories = {"bug", "balance", "ux", "content", "general"}
    if normalized_category not in allowed_categories:
        normalized_category = "general"

    context = {
        "url": body.page_url or "",
        "path": body.page_path or "",
        "mode": body.mode or "",
        "user": body.user_label or "",
        "user_agent": request.headers.get("user-agent", ""),
        "ip": client_ip,
    }

    feedback_doc = {
        "category": normalized_category,
        "message": body.message.strip(),
        "reporter_email": (body.reporter_email or "").strip(),
        "context": context,
        "created_at": datetime.utcnow(),
    }

    try:
        feedback_collection.insert_one(feedback_doc)
    except Exception as exc:
        logger.warning("[FEEDBACK] Failed to persist feedback document: %s", exc)

    sent = send_feedback_email(
        message=feedback_doc["message"],
        category=normalized_category,
        reporter_email=feedback_doc["reporter_email"],
        context=context,
    )
    if not sent:
        logger.warning("[FEEDBACK] Email send failed for category=%s", normalized_category)

    return {"success": True, "email_sent": bool(sent)}
