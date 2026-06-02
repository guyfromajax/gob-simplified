"""
Leaderboard API (non–auth-prefix routes under /api/leaderboard).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from bson import ObjectId

from BackEnd.db import users_collection, franchises_collection, franchise_team_data_collection
from BackEnd.utils.auth import get_current_user
from BackEnd.utils.user_tracking import ARCHETYPE_KEYS

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


def _normalize_team_name_to_slug(team_name: str | None) -> str | None:
    normalized = str(team_name or "").strip().lower().replace("-", " ")
    name_to_slug = {
        "bentley truman": "bentley_truman",
        "lancaster": "lancaster",
        "four corners": "four_corners",
        "ocean city": "ocean_city",
        "morristown": "morristown",
        "little york": "little_york",
        "xavien": "xavien",
        "south lancaster": "south_lancaster",
    }
    return name_to_slug.get(normalized)


@router.get("/by-team")
async def get_leaderboard_by_team(
    view: str = Query("geek_points"),
    user: dict = Depends(get_current_user),
):
    """
    Top 3 users per A1 team by either:
    - geek_points earned for that team (geek_points_by_team), or
    - active franchise natl_rank for that team (lower is better)
    Keys: bentley_truman, lancaster, ... (see A1_SLUG_TO_CANONICAL).
    """
    _ = user  # require auth; same pattern as /api/auth/leaderboard
    requested_view = str(view or "geek_points").strip().lower()

    if requested_view == "rank":
        docs = list(
            users_collection.find(
                {},
                {"username": 1, "email": 1, "lead_archetype": 1},
            )
        )
        usernames_by_user_id = {
            str(doc.get("_id")): _display_username(doc)
            for doc in docs
        }
        lead_by_user_id = {
            str(doc.get("_id")): str(doc.get("lead_archetype") or "")
            for doc in docs
        }
        franchise_docs = list(
            franchises_collection.find(
                {},
                {"_id": 1, "user_id": 1, "user_team_id": 1, "user_team_object_id": 1},
            )
        )
        latest_franchise_by_user_id: dict[str, dict] = {}
        for franchise_doc in franchise_docs:
            user_id = str(franchise_doc.get("user_id") or "").strip()
            if not user_id:
                continue
            existing = latest_franchise_by_user_id.get(user_id)
            if existing is None or franchise_doc["_id"] > existing["_id"]:
                latest_franchise_by_user_id[user_id] = franchise_doc

        result: dict[str, list[dict[str, str | int]]] = {slug: [] for slug in A1_SLUG_TO_CANONICAL}

        for user_id, franchise_doc in latest_franchise_by_user_id.items():
            username = usernames_by_user_id.get(user_id)
            if not username:
                continue

            slug = _normalize_team_name_to_slug(franchise_doc.get("user_team_id"))
            if not slug or slug not in result:
                continue

            team_object_id = str(franchise_doc.get("user_team_object_id") or "").strip()
            if not team_object_id:
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

            raw_rank = ftd_doc.get("natl_rank")
            try:
                natl_rank = int(raw_rank)
            except (TypeError, ValueError):
                continue
            if natl_rank <= 0:
                continue

            result[slug].append({
                "username": username,
                "natl_rank": natl_rank,
                "lead_archetype": lead_by_user_id.get(user_id, ""),
            })

        for slug, entries in result.items():
            entries.sort(key=lambda entry: (int(entry["natl_rank"]), str(entry["username"]).lower()))
            result[slug] = entries[:3]

        return result

    docs = list(
        users_collection.find(
            {},
            {"username": 1, "email": 1, "geek_points_by_team": 1, "lead_archetype": 1},
        )
    )

    result: dict[str, list[dict[str, str | int]]] = {slug: [] for slug in A1_SLUG_TO_CANONICAL}

    for slug, canon_key in A1_SLUG_TO_CANONICAL.items():
        scores: list[tuple[int, str, str, str]] = []
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
            scores.append((pts, uname.lower(), uname, str(doc.get("lead_archetype") or "")))
        scores.sort(key=lambda t: (-t[0], t[1]))
        result[slug] = [
            {"username": uname, "geek_points": pts, "lead_archetype": lead}
            for pts, _lower, uname, lead in scores[:3]
        ]

    return result


@router.get("/by-archetype")
async def get_leaderboard_by_archetype(user: dict = Depends(get_current_user)):
    """Top 5 coaches per coaching archetype, ranked by each coach's personal
    percentage for that archetype (their `archetypes.<key>` ÷ `archetypes.total`).

    Pure percentage, no minimum games. Returns a dict keyed by archetype key →
    list of up to 5 rows `{ rank, username, pct, is_current_user }` (empty list
    when no coach has that archetype yet).
    """
    current_user_id = str(user.get("user_id", "")).strip()
    docs = list(
        users_collection.find(
            {"archetypes.total": {"$gt": 0}},
            {"username": 1, "email": 1, "archetypes": 1},
        )
    )

    boards: dict[str, list] = {k: [] for k in ARCHETYPE_KEYS}
    for doc in docs:
        arche = doc.get("archetypes") or {}
        try:
            total = int(arche.get("total", 0) or 0)
        except (TypeError, ValueError):
            total = 0
        if total <= 0:
            continue
        uname = _display_username(doc)
        uid = str(doc.get("_id"))
        for k in ARCHETYPE_KEYS:
            try:
                count = int(arche.get(k, 0) or 0)
            except (TypeError, ValueError):
                count = 0
            if count <= 0:
                continue
            pct = round(count / total * 100)
            boards[k].append((pct, count, total, uname, uid))

    result: dict[str, list[dict]] = {}
    for k in ARCHETYPE_KEYS:
        # pct desc, then raw count desc, then total desc, then username for a stable order.
        rows = sorted(boards[k], key=lambda t: (-t[0], -t[1], -t[2], t[3].lower()))[:5]
        result[k] = [
            {
                "rank": i + 1,
                "username": uname,
                "pct": pct,
                "is_current_user": (uid == current_user_id),
            }
            for i, (pct, count, total, uname, uid) in enumerate(rows)
        ]
    return result
