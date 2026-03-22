"""
Covert Release — DREB → outlet fast break selection and coordinates.

See docs/To Do/FB_Update_Brief.md. Steal-initiated fast breaks do not use this module.
Coordinates are in HOME orientation (x 0–100); x is mirrored when the future FB offense team is away.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    pass


def _player_x(player: Any, default: float = 50.0) -> float:
    coords = getattr(player, "coords", None) or {}
    if isinstance(coords, dict):
        try:
            return float(coords.get("x", default))
        except (TypeError, ValueError):
            return default
    return default


def get_defender_position_guarding_shooter(
    game: Any,
    shooter: Any,
    def_lineup: Dict[str, Any],
    shot_step_index: Optional[int],
    shooter_pos: Optional[str],
) -> Optional[str]:
    """
    Defensive lineup key (e.g. 'PG') for the defender guarding the shooter.
    Zone: lookup in zone_defender_assignments_by_step. Man: defender at shooter's position.
    """
    shooter_id = getattr(shooter, "player_id", None)
    if shooter_id is not None and shot_step_index is not None and hasattr(game, "zone_defender_assignments_by_step"):
        assignments_by_step = getattr(game, "zone_defender_assignments_by_step", {}) or {}
        assignments = assignments_by_step.get(shot_step_index, {}) or {}
        for def_pos, off_pid in assignments.items():
            if str(off_pid) == str(shooter_id):
                return def_pos
    if shooter_pos and shooter_pos in def_lineup:
        return shooter_pos
    return None


def select_covert_release_position(
    def_lineup: Dict[str, Any],
    game: Any,
    shooter: Any,
    shot_step_index: Optional[int],
    shooter_pos: Optional[str],
    off_team: Any,
) -> Optional[str]:
    """
    Farthest-from-rim defender (by x in HOME orientation), excluding the shooter matchup.
    Home team shooting → away defense → minimize x. Away shooting → home defense → maximize x.
    """
    guard_pos = get_defender_position_guarding_shooter(
        game, shooter, def_lineup, shot_step_index, shooter_pos
    )

    candidates: List[str] = []
    for pos, player in def_lineup.items():
        if player is None:
            continue
        if guard_pos is not None and pos == guard_pos:
            continue
        candidates.append(pos)
    if not candidates:
        candidates = [pos for pos, p in def_lineup.items() if p is not None]
        if guard_pos is not None and len(candidates) > 1:
            candidates = [p for p in candidates if p != guard_pos]
    if not candidates:
        return None

    is_home_shooting = getattr(off_team, "team_id", None) == getattr(game.home_team, "team_id", None)

    best_val: Optional[float] = None
    tied: List[str] = []
    for pos in candidates:
        px = _player_x(def_lineup[pos])
        if is_home_shooting:
            val = px
            if best_val is None or val < best_val:
                best_val = val
                tied = [pos]
            elif val == best_val:
                tied.append(pos)
        else:
            val = px
            if best_val is None or val > best_val:
                best_val = val
                tied = [pos]
            elif val == best_val:
                tied.append(pos)

    return random.choice(tied) if tied else None


def sample_release_coords(good_release: bool, will_be_home_fb_offense: bool) -> Dict[str, int]:
    """Covert Release outlet receiver coords (FB_Update_Brief §5, first bullet)."""
    if good_release:
        x_lo, x_hi, y_lo, y_hi = 45, 55, 18, 32
    else:
        x_lo, x_hi, y_lo, y_hi = 40, 50, 22, 30
    x = random.randint(x_lo, x_hi)
    y = random.randint(y_lo, y_hi)
    if not will_be_home_fb_offense:
        x = 100 - x
    return {"x": x, "y": y}


def sample_getback_coords(good_d: bool, will_be_home_fb_offense: bool) -> Dict[str, int]:
    """Covert Release get-back defender coords (FB_Update_Brief §5, second bullet)."""
    if good_d:
        x_lo, x_hi, y_lo, y_hi = 53, 60, 22, 30
    else:
        x_lo, x_hi, y_lo, y_hi = 45, 60, 18, 32
    x = random.randint(x_lo, x_hi)
    y = random.randint(y_lo, y_hi)
    if not will_be_home_fb_offense:
        x = 100 - x
    return {"x": x, "y": y}
