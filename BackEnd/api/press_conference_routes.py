"""
Post-game press conference (franchise): session creation with real question qualification.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Any, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from BackEnd.db import (
    franchise_state_collection,
    franchises_collection,
    games_collection,
    press_conference_sessions_collection,
)
from BackEnd.pgpc_context import build_franchise_context_for_pgpc
from BackEnd.pgpc_player_slot import (
    answer_name_for_pgpc_answers,
    resolve_player_display_names_for_slot,
)
from BackEnd.pgpc_qualification import get_qualifying_pgpc_questions
from BackEnd.pgpc_selection import select_pgpc_questions_for_session, shuffle_answers_for_display
from BackEnd.pgpc_snapshot_storage import build_pgpc_snapshot
from BackEnd.utils.auth import get_current_user
from BackEnd.utils.ownership import verify_franchise_owned_by_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["press_conference"])

VALID_CHOICES = frozenset({"A", "B", "C", "D", "E"})


def _user_team_from_franchise_doc(franchise_doc: dict[str, Any]) -> tuple[str | None, str | None]:
    user_team_id = franchise_doc.get("user_team_id")
    user_team_object_id = franchise_doc.get("user_team_object_id")
    if user_team_id and user_team_object_id:
        return str(user_team_id), str(user_team_object_id)
    try:
        state = franchise_state_collection.find_one({"_id": "state"}) or {}
        team_name = state.get("team")
        if team_name:
            from BackEnd.db import teams_collection

            team_doc = teams_collection.find_one({"name": team_name})
            if team_doc:
                return str(team_name), str(team_doc["_id"])
    except Exception:
        pass
    return None, None


def _load_game_doc(game_id: str) -> dict[str, Any] | None:
    doc = games_collection.find_one({"_id": game_id})
    if doc:
        return doc
    if ObjectId.is_valid(game_id):
        doc = games_collection.find_one({"_id": ObjectId(game_id)})
        if doc:
            return doc
    return None


def _resolve_user_opponent_team_ids(
    game_doc: dict[str, Any], user_team_object_id: str
) -> tuple[str, str] | None:
    home = str(game_doc.get("home_team_id") or "")
    away = str(game_doc.get("away_team_id") or "")
    uo = str(user_team_object_id)
    if uo and home and uo == home and away:
        return home, away
    if uo and away and uo == away and home:
        return away, home
    side = game_doc.get("user_team_side")
    if side == "home" and home and away:
        return home, away
    if side == "away" and away and home:
        return away, home
    return None


def _prepare_session_questions(
    game_doc: dict[str, Any],
    franchise_doc: dict[str, Any],
    user_id: str,
    franchise_id: str,
    week: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    _ut_name, ut_oid = _user_team_from_franchise_doc(franchise_doc)
    if not ut_oid:
        raise HTTPException(status_code=400, detail="Franchise has no user team")
    pair = _resolve_user_opponent_team_ids(game_doc, ut_oid)
    if not pair:
        raise HTTPException(status_code=400, detail="Could not resolve user/opponent from game")
    user_tid, opp_tid = pair

    ctx = build_franchise_context_for_pgpc(
        game_doc,
        franchise_doc,
        user_team_id=user_tid,
        opponent_team_id=opp_tid,
        user_id=user_id,
        franchise_id=franchise_id,
        week=week,
        attach_db_fields=True,
    )
    qualified = get_qualifying_pgpc_questions(game_doc, ctx)
    qualified_count = len(qualified)
    rng = random.Random()
    selected = select_pgpc_questions_for_session(qualified, rng=rng)
    out: list[dict[str, Any]] = []
    for q in selected:
        disp = shuffle_answers_for_display(q, rng)
        full, first = resolve_player_display_names_for_slot(
            disp.get("player_slot"), game_doc, user_tid, ctx
        )
        text = str(disp.get("text") or "")
        question_had_player_placeholder = "{player_name}" in text
        if full and question_had_player_placeholder:
            text = text.replace("{player_name}", full)
        disp["text"] = text
        answer_token = answer_name_for_pgpc_answers(
            question_included_player_placeholder=question_had_player_placeholder,
            full_name=full,
            first_name=first,
        )
        if full:
            for ans in disp.get("answers") or []:
                if isinstance(ans, dict):
                    at = str(ans.get("text") or "")
                    if "{player_name}" in at:
                        ans["text"] = at.replace("{player_name}", answer_token)
        out.append(disp)
    return out, dict(ctx), qualified_count


class PressConferenceCreateSessionBody(BaseModel):
    franchise_id: str
    week: int = Field(..., ge=1)
    game_id: str | None = None
    question_set_id: str = "bank_v1"


class PressConferenceAnswerBody(BaseModel):
    question_index: int = Field(..., ge=0)
    choice: Literal["A", "B", "C", "D", "E"]


def _session_oid(session_id: str) -> ObjectId:
    try:
        return ObjectId(session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid session_id") from exc


def _dummy_session_questions() -> list[dict[str, Any]]:
    letters = ["A", "B", "C", "D", "E"]
    out: list[dict[str, Any]] = []
    for i in range(1, 11):
        out.append(
            {
                "id": f"dummy_{i}",
                "text": f"Question {i}",
                "player_slot": None,
                "category": "dummy",
                "answers": [{"letter": L, "text": f"Answer {L}", "archetype": None} for L in letters],
            }
        )
    return out


@router.post("/franchise/press-conference/session")
def create_press_conference_session(
    body: PressConferenceCreateSessionBody,
    user: dict = Depends(get_current_user),
):
    verify_franchise_owned_by_user(body.franchise_id, user["user_id"])
    now = datetime.now(timezone.utc)
    try:
        fid = ObjectId(body.franchise_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid franchise_id") from exc

    franchise_doc = franchises_collection.find_one({"_id": fid})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    questions_payload: list[dict[str, Any]]
    pgpc_context: dict[str, Any] | None = None
    qualified_count: int | None = None

    game_doc: dict[str, Any] | None = None
    if body.game_id:
        game_doc = _load_game_doc(str(body.game_id))
        if not game_doc:
            raise HTTPException(status_code=404, detail="Game not found")

    if game_doc:
        try:
            questions_payload, pgpc_context, qualified_count = _prepare_session_questions(
                game_doc,
                franchise_doc,
                str(user["user_id"]),
                str(body.franchise_id),
                int(body.week),
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception("PGPC: failed to build questions for game_id=%s", body.game_id)
            raise HTTPException(
                status_code=500,
                detail="Could not build press conference questions for this game.",
            ) from None
    else:
        questions_payload = _dummy_session_questions()

    doc: dict[str, Any] = {
        "user_id": str(user["user_id"]),
        "franchise_id": fid,
        "week": int(body.week),
        "game_id": body.game_id,
        "question_set_id": body.question_set_id,
        "questions": questions_payload,
        "answers": [],
        "choice_counts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0},
        "status": "in_progress",
        "created_at": now,
        "updated_at": now,
    }
    if pgpc_context is not None:
        doc["pgpc_context"] = pgpc_context
    if qualified_count is not None:
        doc["qualified_question_count"] = qualified_count
    if game_doc is not None and pgpc_context is not None:
        doc["pgpc_snapshot"] = build_pgpc_snapshot(game_doc, pgpc_context)

    result = press_conference_sessions_collection.insert_one(doc)
    return {
        "session_id": str(result.inserted_id),
        "status": "ok",
        "questions": questions_payload,
        "question_count": len(questions_payload),
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

    qs = sess.get("questions") or []
    if not isinstance(qs, list) or body.question_index >= len(qs):
        raise HTTPException(status_code=400, detail="Invalid question_index")

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
