"""
Leaderboard API (non–auth-prefix routes under /api/leaderboard).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from BackEnd.db import users_collection
from BackEnd.utils.auth import get_current_user

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

# Response keys match mode-select.js A1_CONFERENCE_TEAMS[].id; values are users.geek_points_by_team keys.
A1_SLUG_TO_CANONICAL = {
    "bentley_truman": "BENTLEY_TRUMAN",
    "lancaster": "LANCASTER",
    "four_corners": "FOUR_CORNERS",
    "ocean_city": "OCEAN_CITY",
    "morristown": "MORRISTOWN",
    "little_york": "LITTLE_YORK",
    "xavien": "XAVIEN",
    "south_lancaster": "SOUTH_LANCASTER",
}


def _display_username(doc: dict) -> str:
    username = str(doc.get("username") or "").strip()
    if username:
        return username
    email = str(doc.get("email") or "").strip()
    return email.split("@", 1)[0].strip() if email else "Coach"


@router.get("/by-team")
async def get_leaderboard_by_team(user: dict = Depends(get_current_user)):
    """
    Top 3 users per A1 team by geek_points earned for that team (geek_points_by_team).
    Keys: bentley_truman, lancaster, ... (see A1_SLUG_TO_CANONICAL).
    """
    _ = user  # require auth; same pattern as /api/auth/leaderboard
    docs = list(
        users_collection.find(
            {},
            {"username": 1, "email": 1, "geek_points_by_team": 1},
        )
    )

    result: dict[str, list[dict[str, str | int]]] = {slug: [] for slug in A1_SLUG_TO_CANONICAL}

    for slug, canon_key in A1_SLUG_TO_CANONICAL.items():
        scores: list[tuple[int, str, str]] = []
        for doc in docs:
            gbt = doc.get("geek_points_by_team")
            if not isinstance(gbt, dict):
                continue
            raw = gbt.get(canon_key)
            if raw is None:
                continue
            try:
                pts = int(raw)
            except (TypeError, ValueError):
                continue
            if pts <= 0:
                continue
            uname = _display_username(doc)
            scores.append((pts, uname.lower(), uname))
        scores.sort(key=lambda t: (-t[0], t[1]))
        result[slug] = [
            {"username": uname, "geek_points": pts}
            for pts, _lower, uname in scores[:3]
        ]

    return result
