"""
Post-game press conference (franchise): store answers in a dedicated collection.
Dummy question set v1 — structure only; FTD application comes later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from BackEnd.db import press_conference_sessions_collection
from BackEnd.utils.auth import get_current_user
from BackEnd.utils.ownership import verify_franchise_owned_by_user

router = APIRouter(tags=["press_conference"])

VALID_CHOICES = frozenset({"A", "B", "C", "D", "E"})


class PressConferenceCreateSessionBody(BaseModel):
    franchise_id: str
    week: int = Field(..., ge=1)
    game_id: str | None = None
    question_set_id: str = "dummy_v1"


class PressConferenceAnswerBody(BaseModel):
    question_index: int = Field(..., ge=0, le=9)
    choice: Literal["A", "B", "C", "D", "E"]


def _session_oid(session_id: str) -> ObjectId:
    try:
        return ObjectId(session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid session_id") from exc


@router.post("/franchise/press-conference/session")
def create_press_conference_session(
    body: PressConferenceCreateSessionBody,
    user: dict = Depends(get_current_user),
):
    verify_franchise_owned_by_user(body.franchise_id, user["user_id"])
    now = datetime.now(timezone.utc)
    doc: dict[str, Any] = {
        "user_id": str(user["user_id"]),
        "franchise_id": ObjectId(body.franchise_id),
        "week": int(body.week),
        "game_id": body.game_id,
        "question_set_id": body.question_set_id,
        "answers": [],
        "choice_counts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0},
        "status": "in_progress",
        "created_at": now,
        "updated_at": now,
    }
    result = press_conference_sessions_collection.insert_one(doc)
    return {
        "session_id": str(result.inserted_id),
        "status": "ok",
    }


@router.post("/franchise/press-conference/session/{session_id}/answer")
def append_press_conference_answer(
    session_id: str,
    body: PressConferenceAnswerBody,
    user: dict = Depends(get_current_user),
):
    oid = _session_oid(session_id)
    sess = press_conference_sessions_collection.find_one({"_id": oid})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(sess.get("user_id")) != str(user["user_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    if sess.get("status") != "in_progress":
        raise HTTPException(status_code=409, detail="Session is not open for answers")

    choice = body.choice
    if choice not in VALID_CHOICES:
        raise HTTPException(status_code=400, detail="Invalid choice")

    now = datetime.now(timezone.utc)
    inc_key = f"choice_counts.{choice}"
    press_conference_sessions_collection.update_one(
        {"_id": oid},
        {
            "$push": {
                "answers": {
                    "question_index": body.question_index,
                    "choice": choice,
                    "at": now.isoformat(),
                }
            },
            "$inc": {inc_key: 1},
            "$set": {"updated_at": now},
        },
    )
    updated = press_conference_sessions_collection.find_one({"_id": oid}, {"choice_counts": 1})
    counts = (updated or {}).get("choice_counts") or {}
    return {"status": "ok", "choice_counts": counts}


@router.post("/franchise/press-conference/session/{session_id}/complete")
def complete_press_conference_session(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    oid = _session_oid(session_id)
    sess = press_conference_sessions_collection.find_one({"_id": oid})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(sess.get("user_id")) != str(user["user_id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    now = datetime.now(timezone.utc)
    press_conference_sessions_collection.update_one(
        {"_id": oid},
        {"$set": {"status": "completed", "completed_at": now, "updated_at": now}},
    )
    return {"status": "ok"}
