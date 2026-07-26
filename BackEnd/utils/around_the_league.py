"""
Around The League board (Mode Select): last 8 franchise game completions (phase B).

Persists an ordered 8-slot board with the §6 reorder rule. Card fields are hydrated
live from the franchise that owns the stored last game (`franchise_id` frozen at
completion); last_game itself is frozen at completion time.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from BackEnd.db import (
    around_the_league_collection,
    franchises_collection,
    teams_collection,
    users_collection,
)
from BackEnd.utils.community_highlights import (
    _display_username_for_highlight,
    _ftd_team_display,
    _user_regular_season_record,
)
from BackEnd.utils.franchise_geek_points import teams_match_for_franchise

logger = logging.getLogger(__name__)

BOARD_DOC_ID = "global_board"
MAX_SLOTS = 8

# Display labels aligned with franchise-command-center.js EOS_PLAY_CTA_BY_WEEK (FCC copy).
ATL_WEEK_LABELS: dict[int, str] = {
    27: "Conference Tourney First Round",
    28: "Conference Tourney Semifinals",
    29: "Conference Tourney Championship",
    30: "Region Tourney First Round",
    31: "Region Tourney Championship",
    32: "National Tourney First Round",
    33: "National Tourney Semifinals",
    34: "National Championship",
}


def atl_week_label(week: int) -> str:
    wk = int(week or 1)
    if 27 <= wk <= 34:
        return ATL_WEEK_LABELS.get(wk, f"Week {wk}")
    return f"Week {wk}"


def _natl_rank_display(natl_rank: int | None) -> str | None:
    if natl_rank is None:
        return None
    try:
        nr = int(natl_rank)
    except (TypeError, ValueError):
        return None
    if nr <= 0 or nr >= 999:
        return None
    return nr


def _last_game_is_away(
    franchise_doc: dict[str, Any],
    completed_week: int,
    user_team_id_str: str,
) -> bool:
    rows = (franchise_doc.get("results") or {}).get(str(int(completed_week)), []) or []
    ut = str(user_team_id_str or "").strip()
    for row in rows:
        if not isinstance(row, dict):
            continue
        away_id = str(row.get("away_id") or "")
        home_id = str(row.get("home_id") or "")
        if teams_match_for_franchise(away_id, ut):
            return True
        if teams_match_for_franchise(home_id, ut):
            return False
    return False


def _apply_reorder(slots: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    """§6 slot shift: re-entry at slot 1; shift only preceding slots or full push for newcomers."""
    user_id = str(entry.get("user_id") or "")
    k = next((i for i, s in enumerate(slots) if str(s.get("user_id") or "") == user_id), -1)
    if k < 0:
        return [entry] + slots[: MAX_SLOTS - 1]
    return [entry] + slots[:k] + slots[k + 1 :]


def _resolve_next_opponent(
    franchise_doc: dict[str, Any],
    user_team_id_str: str,
) -> dict[str, Any] | None:
    """Structured next opponent, or None when eliminated / no scheduled game."""
    try:
        from BackEnd.api.franchise_routes import _find_user_next_game
    except Exception:
        logger.debug("[ATL] _find_user_next_game import failed", exc_info=True)
        return None

    next_game = _find_user_next_game(franchise_doc, str(user_team_id_str))
    if not next_game:
        return None

    away_id = str(next_game.get("away_team_id") or "")
    home_id = str(next_game.get("home_team_id") or "")
    is_away = teams_match_for_franchise(away_id, user_team_id_str)
    opp_id = home_id if is_away else away_id
    try:
        opp_oid = ObjectId(str(opp_id))
        team_doc = teams_collection.find_one({"_id": opp_oid}, {"name": 1}) or {}
    except Exception:
        team_doc = teams_collection.find_one({"name": opp_id}, {"name": 1}) or {}
    opp_name = str(team_doc.get("name") or opp_id or "?")
    return {"is_away": bool(is_away), "team_name": opp_name}


def _franchise_owned_by(franchise_doc: dict[str, Any], user_id_str: str, user_oid: ObjectId) -> bool:
    owner = franchise_doc.get("user_id")
    if owner is None:
        return False
    if owner == user_oid:
        return True
    return str(owner) == user_id_str


def _row_scores_for_user(row: dict[str, Any], user_team_id_str: str) -> tuple[int, int] | None:
    """Return (user_score, opp_score) for a results row, or None if user not in matchup."""
    ut = str(user_team_id_str or "").strip()
    away_id = str(row.get("away_id") or "")
    home_id = str(row.get("home_id") or "")
    try:
        away_score = int(row.get("away_score") or 0)
        home_score = int(row.get("home_score") or 0)
    except (TypeError, ValueError):
        return None
    if teams_match_for_franchise(away_id, ut):
        return away_score, home_score
    if teams_match_for_franchise(home_id, ut):
        return home_score, away_score
    return None


def _franchise_matches_last_game(franchise_doc: dict[str, Any], last_game: dict[str, Any]) -> bool:
    """Best-effort heal for legacy board rows that lack franchise_id."""
    _, user_team_id_str = _resolve_user_team(franchise_doc)
    if not user_team_id_str:
        return False
    try:
        target_user = int(last_game.get("user_score") or 0)
        target_opp = int(last_game.get("opp_score") or 0)
    except (TypeError, ValueError):
        return False
    opp_name = str(last_game.get("opponent") or "").strip().lower()
    results = franchise_doc.get("results") or {}
    if not isinstance(results, dict):
        return False
    for week_rows in results.values():
        if not isinstance(week_rows, list):
            continue
        for row in week_rows:
            if not isinstance(row, dict):
                continue
            scores = _row_scores_for_user(row, str(user_team_id_str))
            if not scores:
                continue
            user_score, opp_score = scores
            if user_score != target_user or opp_score != target_opp:
                continue
            if not opp_name:
                return True
            for key in ("away_team", "home_team", "team1", "team2", "opponent"):
                val = str(row.get(key) or "").strip().lower()
                if val and val == opp_name:
                    return True
            return True
    return False


def _load_franchises_for_user(user_id_str: str, user_oid: ObjectId) -> list[dict[str, Any]]:
    return list(
        franchises_collection.find(
            {"$or": [{"user_id": user_id_str}, {"user_id": user_oid}]},
        ).sort("_id", -1)
    )


def _resolve_franchise_doc_for_slot(
    stored: dict[str, Any],
    user_id_str: str,
    user_oid: ObjectId,
) -> dict[str, Any] | None:
    """Prefer frozen franchise_id from the completion that produced last_game."""
    fid_raw = stored.get("franchise_id")
    if fid_raw:
        try:
            doc = franchises_collection.find_one({"_id": ObjectId(str(fid_raw))})
            if doc and _franchise_owned_by(doc, user_id_str, user_oid):
                return doc
        except Exception:
            logger.debug("[ATL] invalid franchise_id on board slot: %s", fid_raw, exc_info=True)

    candidates = _load_franchises_for_user(user_id_str, user_oid)
    if not candidates:
        return None

    last_game = stored.get("last_game") if isinstance(stored.get("last_game"), dict) else {}
    if last_game:
        for doc in candidates:
            if _franchise_matches_last_game(doc, last_game):
                return doc

    # Last resort for pre-multi-franchise board rows with no matchable last_game.
    return candidates[0]


def record_around_the_league_completion(
    *,
    owner_user_id: Any,
    franchise_doc: dict[str, Any],
    completed_week: int,
    pending: dict[str, Any],
    user_team_id_str: str,
    opp_name: str,
    user_won: bool,
    user_score: int,
    opponent_score: int,
) -> None:
    """Append/reorder board after phase-B flush (franchise user game only; not tutorial)."""
    if not owner_user_id or not franchise_doc or not pending:
        return

    user_id_str = str(owner_user_id)
    completed_at = datetime.now(timezone.utc).isoformat()
    is_away = _last_game_is_away(franchise_doc, int(completed_week), str(user_team_id_str))
    franchise_id = franchise_doc.get("_id")
    if franchise_id is None:
        return

    stored_entry: dict[str, Any] = {
        "user_id": user_id_str,
        "franchise_id": str(franchise_id),
        "completed_at": completed_at,
        "last_game": {
            "won": bool(user_won),
            "is_away": bool(is_away),
            "opponent": str(opp_name or "?"),
            "user_score": int(user_score),
            "opp_score": int(opponent_score),
        },
    }

    doc = around_the_league_collection.find_one({"_id": BOARD_DOC_ID}) or {}
    slots: list[dict[str, Any]] = list(doc.get("slots") or [])

    # Identical timestamps: randomize relative order among tied entries before reorder.
    tied = [s for s in slots if str(s.get("completed_at") or "") == completed_at]
    if tied:
        random.shuffle(tied)
        other = [s for s in slots if str(s.get("completed_at") or "") != completed_at]
        slots = other + tied

    new_slots = _apply_reorder(slots, stored_entry)[:MAX_SLOTS]

    try:
        around_the_league_collection.update_one(
            {"_id": BOARD_DOC_ID},
            {"$set": {"slots": new_slots, "updated_at": completed_at}},
            upsert=True,
        )
    except Exception:
        logger.exception("[ATL] Failed to persist board entry user_id=%s", user_id_str)


def _hydrate_slot(stored: dict[str, Any]) -> dict[str, Any] | None:
    user_id_str = str(stored.get("user_id") or "")
    if not user_id_str:
        return None

    try:
        user_oid = ObjectId(user_id_str)
    except Exception:
        return None

    user_doc = users_collection.find_one(
        {"_id": user_oid},
        {"username": 1, "email": 1, "lead_archetype": 1},
    )
    franchise_doc = _resolve_franchise_doc_for_slot(stored, user_id_str, user_oid)
    if not franchise_doc:
        return None

    _u_name, user_team_id_str = _resolve_user_team(franchise_doc)
    if not user_team_id_str:
        return None

    franchise_id = ObjectId(str(franchise_doc["_id"]))
    team_name, primary, secondary, natl_rank = _ftd_team_display(franchise_id, str(user_team_id_str))
    record = _user_regular_season_record(franchise_doc, str(user_team_id_str))
    wins, losses = 0, 0
    if "-" in record:
        parts = record.split("-", 1)
        try:
            wins = int(parts[0])
            losses = int(parts[1])
        except (TypeError, ValueError):
            pass

    week = int(franchise_doc.get("week", 1) or 1)
    next_opp = _resolve_next_opponent(franchise_doc, str(user_team_id_str))
    rank_num = _natl_rank_display(natl_rank)
    last_game = stored.get("last_game") if isinstance(stored.get("last_game"), dict) else {}

    return {
        "user_id": user_id_str,
        "franchise_id": str(franchise_id),
        "username": _display_username_for_highlight(user_doc),
        "lead_archetype": str((user_doc or {}).get("lead_archetype") or ""),
        "team_name": team_name,
        "primary_color": primary,
        "secondary_color": secondary,
        "wins": wins,
        "losses": losses,
        "national_rank": rank_num,
        "week": week,
        "week_label": atl_week_label(week),
        "is_tournament_week": 27 <= week <= 34,
        "next_opponent": next_opp,
        "last_game": {
            "won": bool(last_game.get("won")),
            "is_away": bool(last_game.get("is_away")),
            "opponent": str(last_game.get("opponent") or "?"),
            "user_score": int(last_game.get("user_score") or 0),
            "opp_score": int(last_game.get("opp_score") or 0),
        },
        "completed_at": str(stored.get("completed_at") or ""),
    }


def _resolve_user_team(franchise_doc: dict[str, Any]) -> tuple[str | None, str | None]:
    """Avoid import cycle with community_highlights.get_user_team_from_franchise."""
    user_team_id = franchise_doc.get("user_team_id")
    user_team_object_id = franchise_doc.get("user_team_object_id")
    if user_team_id and user_team_object_id:
        return (str(user_team_id), str(user_team_object_id))
    if user_team_object_id:
        return (str(user_team_id or ""), str(user_team_object_id))
    return (None, None)


def list_around_the_league_entries() -> list[dict[str, Any] | None]:
    """Return exactly MAX_SLOTS items (hydrated cards or None for empty slots)."""
    doc = around_the_league_collection.find_one({"_id": BOARD_DOC_ID}) or {}
    stored_slots: list[dict[str, Any]] = list(doc.get("slots") or [])

    hydrated: list[dict[str, Any] | None] = []
    for stored in stored_slots[:MAX_SLOTS]:
        if not isinstance(stored, dict):
            continue
        card = _hydrate_slot(stored)
        if card:
            hydrated.append(card)

    while len(hydrated) < MAX_SLOTS:
        hydrated.append(None)

    return hydrated[:MAX_SLOTS]
