"""
Universal Community Highlights feed (Mode Select). Max 20 entries; oldest dropped on push.

Pending payload is set after phase A (GP delta = users.geek_points after user-game awards minus before).
The public row is appended after phase B completes (when FTD natl_rank is updated for the week).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from BackEnd.db import (
    community_highlights_collection,
    franchise_state_collection,
    franchise_team_data_collection,
    franchises_collection,
    teams_collection,
    users_collection,
)
from BackEnd.utils.franchise_geek_points import teams_match_for_franchise

logger = logging.getLogger(__name__)

FEED_DOC_ID = "global_feed"


def _display_username_for_highlight(user_doc: dict | None) -> str:
    """Match leaderboard naming: users.username, else email local-part, else Coach."""
    if not user_doc:
        return "Coach"
    username = str(user_doc.get("username") or "").strip()
    if username:
        return username
    email = str(user_doc.get("email") or "").strip()
    return email.split("@", 1)[0].strip() if email else "Coach"


def get_user_team_from_franchise_doc(franchise_doc: dict) -> tuple[str | None, str | None]:
    """Same behavior as franchise_routes.get_user_team_from_franchise (no import cycle)."""
    user_team_id = franchise_doc.get("user_team_id")
    user_team_object_id = franchise_doc.get("user_team_object_id")
    if user_team_id and user_team_object_id:
        return (str(user_team_id), str(user_team_object_id))
    try:
        state = franchise_state_collection.find_one({"_id": "state"}) or {}
        team_name = state.get("team")
        if team_name:
            logger.warning(
                "[COMMUNITY_HIGHLIGHTS] franchise_state fallback for team=%s; migrate user_team fields",
                team_name,
            )
            team_doc = teams_collection.find_one({"name": team_name})
            if team_doc:
                return (str(team_name), str(team_doc["_id"]))
    except Exception as e:
        logger.debug("franchise_state not available: %s", e)
    return (None, None)


def _user_geek_points_total(owner_user_id: Any) -> int:
    if not owner_user_id:
        return 0
    try:
        oid = ObjectId(str(owner_user_id))
    except Exception:
        return 0
    u = users_collection.find_one({"_id": oid}, {"geek_points": 1})
    if not u:
        return 0
    return int(u.get("geek_points") or 0)


def user_geek_points_delta_for_user_game_block(
    franchise_doc: dict,
    gp_before: int,
) -> int:
    gp_after = _user_geek_points_total(franchise_doc.get("user_id"))
    return int(gp_after) - int(gp_before)


def user_geek_points_snapshot_for_franchise(franchise_doc: dict) -> int:
    return _user_geek_points_total(franchise_doc.get("user_id"))


def build_community_highlight_pending(
    *,
    week: int,
    user_team_id_str: Any,
    user_row: dict,
    gp_delta: int,
) -> dict[str, Any]:
    ut = str(user_team_id_str or "").strip()
    away_id = str(user_row.get("away_id") or "")
    home_id = str(user_row.get("home_id") or "")
    away_score = int(user_row.get("away_score") or 0)
    home_score = int(user_row.get("home_score") or 0)
    if teams_match_for_franchise(away_id, ut):
        opp = home_id
        user_won = away_score > home_score
    elif teams_match_for_franchise(home_id, ut):
        opp = away_id
        user_won = home_score > away_score
    else:
        logger.warning(
            "[COMMUNITY_HIGHLIGHTS] user team not in saved row away=%s home=%s user=%s",
            away_id,
            home_id,
            ut,
        )
        opp = home_id or away_id
        user_won = False
    return {
        "week": int(week),
        "gp_delta": int(gp_delta),
        "opponent_team_id_str": str(opp),
        "user_won": bool(user_won),
    }


def _ftd_team_display(franchise_id: ObjectId, team_id_str: str) -> tuple[str, str, str, int]:
    """team_name, primary_hex, secondary_hex, natl_rank from FTD with teams fallback."""
    try:
        tid = ObjectId(str(team_id_str).strip())
    except Exception:
        return "?", "#27408E", "#15181f", 999
    ftd = franchise_team_data_collection.find_one(
        {"franchise_id": franchise_id, "team_id": tid},
        {"team_name": 1, "primary_color": 1, "secondary_color": 1, "natl_rank": 1},
    )
    core = teams_collection.find_one({"_id": tid}, {"name": 1, "primary_color": 1, "secondary_color": 1})
    name = (ftd or {}).get("team_name") or (core or {}).get("name") or "?"
    primary = (ftd or {}).get("primary_color") or (core or {}).get("primary_color") or "#27408E"
    secondary = (ftd or {}).get("secondary_color") or (core or {}).get("secondary_color") or "#15181f"
    raw_nr = (ftd or {}).get("natl_rank")
    try:
        nr = int(raw_nr) if raw_nr is not None and str(raw_nr).strip() != "" else 999
    except (TypeError, ValueError):
        nr = 999
    return str(name), str(primary), str(secondary), nr


def _natl_rank_now_ranked_label(natl_rank: int) -> str:
    """Always `#n` or `#--` for copy 'now ranked …'."""
    if natl_rank is None or natl_rank <= 0 or natl_rank >= 999:
        return "#--"
    return f"#{int(natl_rank)}"


def flush_community_highlight_pending_after_week(
    franchise_id: ObjectId,
    completed_week: int,
) -> None:
    """If franchise has community_highlight_pending for this week, append feed row and unset pending."""
    fresh = franchises_collection.find_one({"_id": franchise_id})
    if not fresh:
        return
    pending = (fresh.get("post_game_status") or {}).get("community_highlight_pending")
    if not pending or int(pending.get("week", -1)) != int(completed_week):
        return

    owner_id = fresh.get("user_id")
    user_doc = None
    if owner_id:
        try:
            user_doc = users_collection.find_one(
                {"_id": ObjectId(str(owner_id))},
                {"username": 1, "email": 1},
            )
        except Exception:
            user_doc = None
    display_username = _display_username_for_highlight(user_doc)

    _u_name, user_team_id_str = get_user_team_from_franchise_doc(fresh)
    if not user_team_id_str:
        logger.warning("[COMMUNITY_HIGHLIGHTS] No user team; skip flush franchise=%s", franchise_id)
        franchises_collection.update_one(
            {"_id": franchise_id},
            {"$unset": {"post_game_status.community_highlight_pending": ""}},
        )
        return

    ut_name, primary, secondary, natl_rank = _ftd_team_display(franchise_id, str(user_team_id_str))

    opp_id = pending.get("opponent_team_id_str")
    opp_name = "?"
    if opp_id:
        opp_name, _, _, _ = _ftd_team_display(franchise_id, str(opp_id))

    user_won = bool(pending.get("user_won"))
    gp_delta = int(pending.get("gp_delta") or 0)
    rank_label = _natl_rank_now_ranked_label(natl_rank)

    now = datetime.now(timezone.utc)
    entry = {
        "at": now.isoformat(),
        "username": display_username,
        "user_team_name": ut_name,
        "opponent_name": opp_name,
        "user_won": user_won,
        "natl_rank": natl_rank,
        "rank_label": rank_label,
        "gp_delta": gp_delta,
        "primary_color": primary,
        "secondary_color": secondary,
    }

    try:
        community_highlights_collection.update_one(
            {"_id": FEED_DOC_ID},
            {
                "$push": {
                    "entries": {
                        "$each": [entry],
                        "$position": 0,
                        "$slice": 20,
                    }
                },
                "$setOnInsert": {"_id": FEED_DOC_ID},
            },
            upsert=True,
        )
    except Exception:
        logger.exception("[COMMUNITY_HIGHLIGHTS] Failed to push entry")

    franchises_collection.update_one(
        {"_id": franchise_id},
        {"$unset": {"post_game_status.community_highlight_pending": ""}},
    )


def list_community_highlight_entries() -> list[dict[str, Any]]:
    doc = community_highlights_collection.find_one({"_id": FEED_DOC_ID})
    if not doc:
        return []
    return list(doc.get("entries") or [])
