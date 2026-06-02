"""
Franchise mode: award geek_points on the owning user's document when their team wins or loses.

Point ranges are documented in docs/docs_1_systems/00_General_Systems/Geek_Points_System.md
"""
from __future__ import annotations

import logging
import random
from typing import Any

from bson import ObjectId

from BackEnd.db import db, users_collection
from BackEnd.tournament import franchise_tournament as ft

logger = logging.getLogger(__name__)


def _resolve_to_object_id_str(team_ref: Any) -> str | None:
    if team_ref is None:
        return None
    s = str(team_ref).strip()
    if not s:
        return None
    if ObjectId.is_valid(s):
        try:
            return str(ObjectId(s))
        except Exception:
            pass
    doc = db.teams.find_one(
        {"$or": [{"team_id": s}, {"name": s}, {"code": s}]},
        {"_id": 1},
    )
    if doc:
        return str(doc["_id"])
    return None


def geek_points_team_key_for_franchise_user(user_team_object_id_str: str | None) -> str | None:
    """
    Canonical key for users.geek_points_by_team (teams.team_id, e.g. LANCASTER).
    Falls back to str(ObjectId) if team_id is missing on the team document.
    """
    if not user_team_object_id_str:
        return None
    try:
        oid = ObjectId(str(user_team_object_id_str).strip())
    except Exception:
        return None
    doc = db.teams.find_one({"_id": oid}, {"team_id": 1})
    if not doc:
        return None
    tid = doc.get("team_id")
    if isinstance(tid, str) and tid.strip():
        return tid.strip()
    return str(oid)


def teams_match_for_franchise(team_a: Any, team_b: Any) -> bool:
    if team_a is None or team_b is None:
        return False
    if str(team_a) == str(team_b):
        return True
    oid_a = _resolve_to_object_id_str(team_a)
    oid_b = _resolve_to_object_id_str(team_b)
    return bool(oid_a and oid_b and oid_a == oid_b)


def franchise_win_geek_points_delta(week: int, eos_game: dict | None) -> int:
    """Return random GP delta for a qualifying win, or 0 if no rule applies."""
    if week <= ft.REGULAR_SEASON_WEEKS:
        return random.randint(5, 15)

    if not eos_game:
        return 0

    phase = eos_game.get("phase")
    rnd = int(eos_game.get("round") or 0)

    if phase == "conference":
        if rnd in (1, 2):
            return random.randint(15, 20)
        if rnd == 3:
            return random.randint(25, 35)
    elif phase == "region":
        return random.randint(40, 50)
    elif phase == "national":
        if rnd in (1, 2):
            return random.randint(50, 75)
        if rnd == 3:
            return random.randint(125, 175)

    return 0


def franchise_loss_geek_points_delta() -> int:
    """Random GP for a franchise game loss (user's team played and did not win)."""
    return random.randint(1, 2)


def apply_bulk_sim_geek_points_policy(delta: int, *, bulk_sim_used: bool = False) -> int:
    """Apply user gameplay-mode GP policy to a final base delta.

    Bulk-sim games keep the existing base award. Games without Sim Full Game /
    Sim Rest of Game receive a 2x award.
    """
    if delta <= 0:
        return 0
    return delta if bulk_sim_used else delta * 2


def maybe_award_franchise_loss_geek_points(
    *,
    owner_user_id: str | None,
    user_team_id_str: str | None,
    winner_team_id: Any,
    participant_team_ids: tuple[Any, ...] | list[Any] | None,
    bulk_sim_used: bool = False,
) -> None:
    """Increment geek_points when the user's franchise team loses a game they participated in."""
    if not owner_user_id or not user_team_id_str:
        return
    if not participant_team_ids:
        return
    if teams_match_for_franchise(winner_team_id, user_team_id_str):
        return
    played = any(teams_match_for_franchise(p, user_team_id_str) for p in participant_team_ids)
    if not played:
        return

    delta = apply_bulk_sim_geek_points_policy(
        franchise_loss_geek_points_delta(),
        bulk_sim_used=bulk_sim_used,
    )
    if delta <= 0:
        return

    try:
        oid = ObjectId(owner_user_id)
    except Exception:
        logger.warning("Invalid owner_user_id for geek_points loss increment: %s", owner_user_id)
        return

    team_key = geek_points_team_key_for_franchise_user(user_team_id_str)
    inc_fields: dict[str, int] = {"geek_points": delta}
    if team_key:
        inc_fields[f"geek_points_by_team.{team_key}"] = delta
    else:
        logger.warning(
            "geek_points_by_team not incremented (loss); could not resolve team key (user_team_id_str=%r)",
            user_team_id_str,
        )

    users_collection.update_one({"_id": oid}, {"$inc": inc_fields})


def maybe_award_franchise_win_geek_points(
    *,
    owner_user_id: str | None,
    user_team_id_str: str | None,
    winner_team_id: Any,
    week: int,
    eos_game_meta: dict | None,
    bulk_sim_used: bool = False,
) -> None:
    if not owner_user_id or not user_team_id_str:
        return
    if not teams_match_for_franchise(winner_team_id, user_team_id_str):
        return

    delta = apply_bulk_sim_geek_points_policy(
        franchise_win_geek_points_delta(week, eos_game_meta),
        bulk_sim_used=bulk_sim_used,
    )
    if delta <= 0:
        return

    try:
        oid = ObjectId(owner_user_id)
    except Exception:
        logger.warning("Invalid owner_user_id for geek_points increment: %s", owner_user_id)
        return

    team_key = geek_points_team_key_for_franchise_user(user_team_id_str)
    inc_fields: dict[str, int] = {"geek_points": delta}
    if team_key:
        # Dot path creates geek_points_by_team and the sub-key on first $inc (lazy).
        inc_fields[f"geek_points_by_team.{team_key}"] = delta
    else:
        logger.warning(
            "geek_points_by_team not incremented; could not resolve team key (user_team_id_str=%r)",
            user_team_id_str,
        )

    users_collection.update_one({"_id": oid}, {"$inc": inc_fields})
