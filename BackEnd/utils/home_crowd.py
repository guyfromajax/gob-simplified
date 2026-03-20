"""
Home Crowd Factor (per game). See docs/docs_1_systems/05_GP_Supporting_Systems/Home_Crowd_System.md

Roll Uses home team team_chemistry (7–25). Effects apply only in-memory for that game.
Upper Bonus Range (training) is reserved for a future update.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict

from BackEnd.constants import FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE

if TYPE_CHECKING:
    pass


def roll_home_crowd_factor(team_chemistry: int) -> int:
    """
    Roll crowd level 1–5 from home team team_chemistry band.
    Values outside 7–25 are clamped.
    """
    tc = max(7, min(25, int(team_chemistry)))
    if tc <= 10:
        weights = [30, 40, 15, 10, 5]
    elif tc <= 15:
        weights = [20, 30, 25, 15, 10]
    elif tc <= 20:
        weights = [10, 20, 30, 20, 20]
    else:  # 21–25
        weights = [5, 15, 20, 30, 30]
    return random.choices([1, 2, 3, 4, 5], weights=weights, k=1)[0]


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
    # factor == 5
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


def initialize_home_crowd_in_game_state(game_state: Dict[str, Any], home_team) -> None:
    """Set home_crowd_* keys from home_team.team_attributes (call once after game_state exists)."""
    tc_raw = home_team.team_attributes.get("team_chemistry", 8)
    try:
        tc = int(tc_raw)
    except (TypeError, ValueError):
        tc = 8
    factor = roll_home_crowd_factor(tc)
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
        return 0.3
    if factor >= 4:
        return 0.2
    return FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE
