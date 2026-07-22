"""
Home Crowd Factor (per game). See docs/docs_1_systems/05_GP_Supporting_Systems/Home_Crowd_System.md

Roll uses home team team_chemistry (7–25) weight bands from that doc. Effects apply only in-memory for the game.

Franchise: Community Engagement (culture-builder-community) can shift which band is used (or Upper Bonus);
see Training_System.md. Pending flags live on franchise_team_data ``pending_community_engagement`` and are
consumed when a franchise game is started (init-game / new simulate-quarter game).
"""
from __future__ import annotations

from BackEnd.utils.sim_random import sim_rng as random
from typing import Any, Dict, List, Tuple

from BackEnd.constants import FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE

# --- Weight tables (source of truth: Home_Crowd_System.md) ---
_CROWD_WEIGHTS_BY_BAND: List[List[int]] = [
    [30, 40, 15, 10, 5],  # Team Chemistry 7–10
    [20, 30, 25, 15, 10],  # 11–15
    [10, 20, 30, 20, 20],  # 16–20
    [5, 15, 20, 30, 30],  # 21–25
]
_UPPER_BONUS_WEIGHTS: List[int] = [0, 10, 20, 30, 40]  # Upper Bonus Range; level 1 never rolled


def _clamp_team_chemistry(tc: int) -> int:
    return max(7, min(25, int(tc)))


def band_index_from_team_chemistry(tc: int) -> int:
    tc = _clamp_team_chemistry(tc)
    if tc <= 10:
        return 0
    if tc <= 15:
        return 1
    if tc <= 20:
        return 2
    return 3


def crowd_weights_for_home_team_chemistry(team_chemistry: int, crowd_shift: str = "none") -> List[int]:
    """
    Return length-5 weights for rolling home crowd factor 1–5.
    crowd_shift: ``none`` | ``up`` | ``down`` (Community Engagement band shift vs actual home chemistry).
    """
    tc = _clamp_team_chemistry(team_chemistry)
    bi = band_index_from_team_chemistry(tc)
    shift = (crowd_shift or "none").lower()
    if shift not in ("none", "up", "down"):
        shift = "none"
    if shift == "none":
        return list(_CROWD_WEIGHTS_BY_BAND[bi])
    if shift == "up":
        if bi >= 3:
            return list(_UPPER_BONUS_WEIGHTS)
        return list(_CROWD_WEIGHTS_BY_BAND[bi + 1])
    # down
    if bi <= 0:
        return list(_CROWD_WEIGHTS_BY_BAND[0])
    return list(_CROWD_WEIGHTS_BY_BAND[bi - 1])


def roll_home_crowd_factor(team_chemistry: int, crowd_shift: str = "none") -> int:
    weights = crowd_weights_for_home_team_chemistry(team_chemistry, crowd_shift)
    return random.choices([1, 2, 3, 4, 5], weights=weights, k=1)[0]


def community_engagement_crowd_shift(user_ce: bool, cpu_ce: bool, user_is_home: bool) -> str:
    """Single-match shift for home crowd weights: ``none``, ``up``, or ``down``."""
    if user_ce and cpu_ce:
        return "none"
    if user_ce and user_is_home:
        return "up"
    if user_ce and not user_is_home:
        return "down"
    if cpu_ce and not user_is_home:
        return "up"
    if cpu_ce and user_is_home:
        return "down"
    return "none"


def _team_object_ids_for_names(home_team_name: str, away_team_name: str) -> Tuple[Any, Any]:
    from BackEnd.db import teams_collection

    home_doc = teams_collection.find_one({"name": home_team_name}, {"_id": 1})
    away_doc = teams_collection.find_one({"name": away_team_name}, {"_id": 1})
    home_oid = home_doc["_id"] if home_doc else None
    away_oid = away_doc["_id"] if away_doc else None
    return home_oid, away_oid


def consume_franchise_community_engagement_for_matchup(
    franchise_id: Any,
    home_team_name: str,
    away_team_name: str,
    user_team_side: str | None,
) -> str:
    """
    Franchise only: read pending Community Engagement on both FTDs, compute crowd_shift, clear both flags.
    If ``user_team_side`` is missing, returns ``none`` (cannot resolve user vs cpu CE cancellation).
    """
    if not franchise_id or not user_team_side:
        return "none"
    from bson import ObjectId

    from BackEnd.db import franchise_team_data_collection

    try:
        fid_oid = ObjectId(str(franchise_id))
    except Exception:
        return "none"
    home_oid, away_oid = _team_object_ids_for_names(home_team_name, away_team_name)
    if home_oid is None or away_oid is None:
        return "none"

    team_q = {"team_id": {"$in": [home_oid, away_oid]}}
    docs = list(
        franchise_team_data_collection.find(
            {"$or": [{"franchise_id": fid_oid, **team_q}, {"franchise_id": str(franchise_id), **team_q}]},
            {"team_id": 1, "pending_community_engagement": 1},
        )
    )
    pending_by_tid = {}
    for d in docs:
        tid = d.get("team_id")
        key = str(tid)
        pending_by_tid[key] = pending_by_tid.get(key, False) or bool(d.get("pending_community_engagement"))

    home_p = pending_by_tid.get(str(home_oid), False)
    away_p = pending_by_tid.get(str(away_oid), False)
    user_is_home = user_team_side == "home"
    user_ce = home_p if user_is_home else away_p
    cpu_ce = away_p if user_is_home else home_p
    shift = community_engagement_crowd_shift(user_ce, cpu_ce, user_is_home)

    franchise_team_data_collection.update_many(
        {"$or": [{"franchise_id": fid_oid, **team_q}, {"franchise_id": str(franchise_id), **team_q}]},
        {"$set": {"pending_community_engagement": False}},
    )
    return shift


def _shot_threshold_deltas_for_factor(factor: int) -> tuple[int, int]:
    """Return (away_delta, home_delta) for shot threshold; higher threshold = harder FG."""
    if factor <= 1:
        return 0, 0
    if factor == 2:
        return 0, 0
    if factor == 3:
        return 25, 0
    if factor == 4:
        return 50, 0
    return 50, -50


HOME_CROWD_PERSIST_KEYS = (
    "home_crowd_factor",
    "home_crowd_away_shot_threshold_delta",
    "home_crowd_home_shot_threshold_delta",
)


def restore_home_crowd_from_saved(game_state: Dict[str, Any], saved: Dict[str, Any]) -> None:
    """If present on a loaded game document, reapply crowd (avoid re-roll on resume)."""
    for key in HOME_CROWD_PERSIST_KEYS:
        if key in saved and saved[key] is not None:
            game_state[key] = saved[key]


def initialize_home_crowd_in_game_state(
    game_state: Dict[str, Any],
    home_team,
    crowd_shift: str = "none",
) -> None:
    """Set home_crowd_* keys from home_team.team_attributes (call once after game_state exists)."""
    tc_raw = home_team.team_attributes.get("team_chemistry", 8)
    try:
        tc = int(tc_raw)
    except (TypeError, ValueError):
        tc = 8
    factor = roll_home_crowd_factor(tc, crowd_shift=crowd_shift)
    away_d, home_d = _shot_threshold_deltas_for_factor(factor)
    game_state["home_crowd_factor"] = factor
    game_state["home_crowd_away_shot_threshold_delta"] = away_d
    game_state["home_crowd_home_shot_threshold_delta"] = home_d


def home_crowd_shot_threshold_delta_for_offense(off_team, game) -> int:
    """Additive crowd adjustment for the offensive team's FG shot threshold this attempt."""
    gs = game.game_state
    if getattr(off_team, "is_home_team", False):
        return int(gs.get("home_crowd_home_shot_threshold_delta", 0) or 0)
    return int(gs.get("home_crowd_away_shot_threshold_delta", 0) or 0)


def effective_ft_miss_to_make_second_chance(game, offense_team_at_line) -> float:
    """
    Probability to upgrade FT miss → make after primary roll.
    Home shooters use global default; away shooters use crowd tiers 2–5.
    """
    if getattr(offense_team_at_line, "is_home_team", False):
        return FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE
    factor = int(game.game_state.get("home_crowd_factor", 1) or 1)
    if factor <= 1:
        return FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE
    if factor in (2, 3):
        return 0.4
    if factor >= 4:
        return 0.3
    return FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE
