"""HCO offensive get-back player selection."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set

from BackEnd.constants import HCO_STRING_SPOTS, HOME_RIM_COORDS, AWAY_RIM_COORDS
from BackEnd.utils.defense_utils import is_zone_defense

GETBACK_QUALIFYING_SPOTS: Set[str] = frozenset(
    {
        "key",
        "deep key",
        "upper midwing",
        "lower midwing",
        "upper wing",
        "lower wing",
        "upper midcorner",
        "lower midcorner",
        "upper corner",
        "lower corner",
        "deep upper wing",
        "deep lower wing",
        "deep upper baseline",
        "deep lower baseline",
    }
)
_QUALIFYING_NORMALIZED = frozenset(_s.replace(" ", "") for _s in GETBACK_QUALIFYING_SPOTS)

_OFFENSE_GETBACK_CHANCES = {
    0: {"none": 1.0, "one": 0.0, "two": 0.0},
    1: {"none": 0.5, "one": 0.5, "two": 0.0},
    2: {"none": 0.25, "one": 0.75, "two": 0.0},
    3: {"none": 0.1, "one": 0.8, "two": 0.1},
    4: {"none": 0.0, "one": 0.5, "two": 0.5},
}


def _norm_spot(spot: Optional[str]) -> str:
    return (spot or "").strip().lower().replace(" ", "")


def _is_qualifying_spot(spot: Optional[str]) -> bool:
    if not spot:
        return False
    return _norm_spot(spot) in _QUALIFYING_NORMALIZED


def _player_xy(player: Any) -> tuple[float, float]:
    coords = getattr(player, "coords", None) or {}
    try:
        return float(coords.get("x", 50.0)), float(coords.get("y", 25.0))
    except (TypeError, ValueError):
        return 50.0, 25.0


def _nearest_spot_name(coords: Dict[str, float]) -> Optional[str]:
    best_name: Optional[str] = None
    best_dist = float("inf")
    cx = float(coords.get("x", 50.0))
    cy = float(coords.get("y", 25.0))
    for name, spot in HCO_STRING_SPOTS.items():
        sx = float(spot.get("x", 50.0))
        sy = float(spot.get("y", 25.0))
        dist = math.hypot(cx - sx, cy - sy)
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name


def _spot_from_skeleton_step(
    steps: List[Dict[str, Any]],
    step_index: Optional[int],
    pos: str,
) -> Optional[str]:
    if step_index is None or not steps or step_index >= len(steps):
        return None
    info = (steps[step_index].get("pos_actions") or {}).get(pos) or {}
    return info.get("location") or info.get("spot")


def _def_pos_for_offensive_player(
    *,
    game: Any,
    off_pos: str,
    off_player: Any,
    def_lineup: Dict[str, Any],
    shot_step_index: Optional[int],
    defense_playcall: str,
) -> Optional[str]:
    if is_zone_defense(defense_playcall):
        assignments_by_step = getattr(game, "zone_defender_assignments_by_step", {}) or {}
        assignments = assignments_by_step.get(shot_step_index, {}) if shot_step_index is not None else {}
        off_id = getattr(off_player, "player_id", None)
        if off_id is not None:
            for def_pos, guarded_id in assignments.items():
                if str(guarded_id) == str(off_id):
                    return def_pos
        return None
    if off_pos in def_lineup and def_lineup.get(off_pos) is not None:
        return off_pos
    return None


def _matchup_spot_at_shot(
    *,
    def_player: Any,
    def_pos: str,
    roles: Dict[str, Any],
    shot_step_index: Optional[int],
) -> Optional[str]:
    steps = roles.get("steps") or []
    skeleton_spot = _spot_from_skeleton_step(steps, shot_step_index, def_pos)
    if skeleton_spot:
        return skeleton_spot
    coords = getattr(def_player, "coords", None) or {}
    if isinstance(coords, dict) and coords.get("x") is not None:
        return _nearest_spot_name(coords)
    return None


def _backcourt_distance_from_basket(x: float, *, is_home_team_shooting: bool) -> float:
    """Larger value = farther from the attacking basket (more 'back')."""
    if is_home_team_shooting:
        return float(HOME_RIM_COORDS["x"]) - float(x)
    return float(x) - float(AWAY_RIM_COORDS["x"])


def roll_num_getback(offense_reb_value: int, rng: float) -> int:
    """Map rebounding slider (0-4) + uniform draw to 0, 1, or 2 get-back players."""
    try:
        level = int(offense_reb_value)
    except (TypeError, ValueError):
        level = 2
    chances = _OFFENSE_GETBACK_CHANCES.get(level, _OFFENSE_GETBACK_CHANCES[2])
    if rng < chances["none"]:
        return 0
    if rng < chances["none"] + chances["one"]:
        return 1
    return 2


def select_offense_getback_list(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    game: Any,
    roles: Dict[str, Any],
    shooter_pos: Optional[str],
    num_getback: int,
    shot_step_index: Optional[int],
    is_home_team_shooting: bool,
    defense_playcall: str,
    shooter_id: Optional[str] = None,
) -> List[str]:
    """
    Pick up to ``num_getback`` offensive positions to retreat.

    Eligibility: shooter excluded by position and player id; defensive matchup
    must be at a qualifying 3pt/deep spot. Among eligible players, choose those
    farthest from the attacking basket on x (1-2 based on roll).
    """
    if num_getback <= 0 or not shooter_pos:
        return []

    shooter_id_str = str(shooter_id) if shooter_id is not None else None
    if not shooter_id_str:
        shooter_obj = roles.get("shooter") if isinstance(roles, dict) else None
        role_shooter_id = getattr(shooter_obj, "player_id", None)
        shooter_id_str = str(role_shooter_id) if role_shooter_id is not None else None

    eligible: List[tuple[str, float]] = []
    for off_pos, off_player in off_lineup.items():
        off_player_id = getattr(off_player, "player_id", None) if off_player else None
        if (
            not off_player
            or off_pos == shooter_pos
            or (shooter_id_str and str(off_player_id) == shooter_id_str)
        ):
            continue
        def_pos = _def_pos_for_offensive_player(
            game=game,
            off_pos=off_pos,
            off_player=off_player,
            def_lineup=def_lineup,
            shot_step_index=shot_step_index,
            defense_playcall=defense_playcall,
        )
        if not def_pos:
            continue
        def_player = def_lineup.get(def_pos)
        if not def_player:
            continue
        matchup_spot = _matchup_spot_at_shot(
            def_player=def_player,
            def_pos=def_pos,
            roles=roles,
            shot_step_index=shot_step_index,
        )
        if not _is_qualifying_spot(matchup_spot):
            continue
        ox, _ = _player_xy(off_player)
        eligible.append((off_pos, _backcourt_distance_from_basket(ox, is_home_team_shooting=is_home_team_shooting)))

    eligible.sort(key=lambda item: item[1], reverse=True)
    return [pos for pos, _ in eligible[:num_getback]]
