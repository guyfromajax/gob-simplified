"""Fast Break drive-cutoff geo helpers (Phase 0).

Pure functions for distance, label proximity, shoot/pass geo gates, FB contest
checks, after-steal meet validation, and POS_O shimmy knot placement.

Spec: ``_documentation_master/06_Gameplay_Systems/Fast_Break_System.md``
(section FB Drive Cutoff & Stop Decision).
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

from BackEnd.constants import CONTEST_EUCLIDEAN_RADIUS, HCO_STRING_SPOTS
from BackEnd.constants.fast_break_constants import (
    FB_CONTEST_MAX_X_TRAIL,
    FB_PASS_GEO_SPOT_LABELS,
    FB_POS_O_SHIMMY_MAGNITUDE,
    FB_SHOOT_GEO_RADIUS,
    FB_SHOOT_GEO_SPOT_LABELS,
)
from BackEnd.utils.animation_step_helpers import _euclid
from BackEnd.utils.animation_step_schema import GridCoord

GridCoordDict = Dict[str, float]

_HOME_BASKET_X = 91.0
_AWAY_BASKET_X = 9.0
_GRID_X_MIN = 4.0
_GRID_X_MAX = 97.0
_GRID_Y_MIN = 1.0
_GRID_Y_MAX = 49.0


def attacking_basket_coord(*, is_away_offense: bool) -> GridCoordDict:
    """Attacking basket in HOME grid orientation."""
    x = _AWAY_BASKET_X if is_away_offense else _HOME_BASKET_X
    return {"x": float(x), "y": 25.0}


def euclidean_to_basket(coord: GridCoordDict, *, is_away_offense: bool) -> float:
    """Euclidean grid distance from ``coord`` to the attacking basket."""
    basket = attacking_basket_coord(is_away_offense=is_away_offense)
    return _euclid(coord, basket)


def nearest_spot_label(coord: GridCoordDict) -> str:
    """Nearest ``HCO_STRING_SPOTS`` label by Euclidean distance (HOME orientation)."""
    cx = float(coord.get("x", 50.0))
    cy = float(coord.get("y", 25.0))
    best_name = "key"
    best_dist = float("inf")
    for name, spot in HCO_STRING_SPOTS.items():
        sx = float(spot.get("x", 50.0))
        sy = float(spot.get("y", 25.0))
        dist = math.hypot(cx - sx, cy - sy)
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name


def _clamp_grid(coord: GridCoordDict) -> GridCoordDict:
    return {
        "x": float(max(_GRID_X_MIN, min(_GRID_X_MAX, float(coord["x"])))),
        "y": float(max(_GRID_Y_MIN, min(_GRID_Y_MAX, float(coord["y"])))),
    }


def fb_shoot_geo_eligible(coord: GridCoordDict, *, is_away_offense: bool) -> bool:
    """True when BH may shoot from a stop (≤24 to basket or shoot spot-label)."""
    if euclidean_to_basket(coord, is_away_offense=is_away_offense) <= FB_SHOOT_GEO_RADIUS:
        return True
    return nearest_spot_label(coord) in FB_SHOOT_GEO_SPOT_LABELS


def fb_pass_receiver_geo_eligible(coord: GridCoordDict, *, is_away_offense: bool) -> bool:
    """True when a teammate is a valid stop-decision pass target by location."""
    if euclidean_to_basket(coord, is_away_offense=is_away_offense) <= FB_SHOOT_GEO_RADIUS:
        return True
    return nearest_spot_label(coord) in FB_PASS_GEO_SPOT_LABELS


def defender_x_trail_spots(
    defender_x: float, shooter_x: float, *, is_away_offense: bool
) -> float:
    """X grid spots the defender trails the shooter (0 if even or ahead)."""
    if is_away_offense:
        return max(0.0, float(defender_x) - float(shooter_x))
    return max(0.0, float(shooter_x) - float(defender_x))


def fb_defender_contests_shot(
    defender_pos: GridCoordDict,
    shooter_pos: GridCoordDict,
    *,
    is_away_offense: bool,
) -> bool:
    """FB contest: within 11 Euclidean and x-trail ≤ 3 (FB-only rule)."""
    if _euclid(defender_pos, shooter_pos) > CONTEST_EUCLIDEAN_RADIUS:
        return False
    trail = defender_x_trail_spots(
        defender_pos["x"], shooter_pos["x"], is_away_offense=is_away_offense
    )
    return trail <= FB_CONTEST_MAX_X_TRAIL


def steal_meet_x_ahead_valid(
    meet: GridCoordDict,
    bh_start: GridCoordDict,
    *,
    is_away_offense: bool,
) -> bool:
    """After-steal only: meet must be ≥1 x toward basket from BH drive-step start."""
    meet_x = float(meet["x"])
    start_x = float(bh_start["x"])
    if is_away_offense:
        return meet_x <= start_x - 1.0
    return meet_x >= start_x + 1.0


def _distance_to_stopper(point: GridCoordDict, stopper: GridCoordDict) -> float:
    return _euclid(point, stopper)


def _apply_axis_offset(
    meet: GridCoordDict,
    stopper: GridCoordDict,
    *,
    axis: str,
    delta: float,
) -> GridCoordDict:
    mx, my = float(meet["x"]), float(meet["y"])
    if axis == "y":
        candidates = (
            {"x": mx, "y": my + delta},
            {"x": mx, "y": my - delta},
        )
    else:
        candidates = (
            {"x": mx + delta, "y": my},
            {"x": mx - delta, "y": my},
        )
    best = max(candidates, key=lambda c: _distance_to_stopper(c, stopper))
    return _clamp_grid(best)


def compute_pos_o_shimmy_point(
    meet: GridCoordDict,
    stopper: GridCoordDict,
    drive_dx: float,
    drive_dy: float,
    *,
    magnitude: float = FB_POS_O_SHIMMY_MAGNITUDE,
) -> GridCoordDict:
    """POS_O dodge knot: 2 grid spots away from stopper along drive-appropriate axis.

    - Mostly horizontal drive (|dx| ≥ |dy|): ±magnitude on **y**
    - Mostly vertical drive (|dy| > |dx|): ±magnitude on **x**
    - Arc / diagonal: perpendicular to drive, scaled to ``magnitude`` Euclidean

    Sign picks the side that increases separation from ``stopper`` at ``meet``.
    """
    adx = abs(float(drive_dx))
    ady = abs(float(drive_dy))
    mag = float(magnitude)

    if adx < 1e-9 and ady < 1e-9:
        return _apply_axis_offset(meet, stopper, axis="y", delta=mag)

    if ady > adx:
        return _apply_axis_offset(meet, stopper, axis="x", delta=mag)
    if adx > ady:
        return _apply_axis_offset(meet, stopper, axis="y", delta=mag)

    # |dx| == |dy| — arc / diagonal: perpendicular dodge
    return compute_perpendicular_shimmy_point(
        meet, stopper, drive_dx, drive_dy, magnitude=mag
    )


def compute_pos_o_shimmy_from_segment(
    meet: GridCoordDict,
    stopper: GridCoordDict,
    segment_from: GridCoordDict,
    *,
    magnitude: float = FB_POS_O_SHIMMY_MAGNITUDE,
) -> GridCoordDict:
    """Shimmy using drive direction from ``segment_from`` → ``meet``."""
    drive_dx = float(meet["x"]) - float(segment_from["x"])
    drive_dy = float(meet["y"]) - float(segment_from["y"])
    return compute_pos_o_shimmy_point(
        meet, stopper, drive_dx, drive_dy, magnitude=magnitude
    )


def compute_perpendicular_shimmy_point(
    meet: GridCoordDict,
    stopper: GridCoordDict,
    drive_dx: float,
    drive_dy: float,
    *,
    magnitude: float = FB_POS_O_SHIMMY_MAGNITUDE,
) -> GridCoordDict:
    """Force perpendicular dodge (arc case) regardless of axis dominance."""
    dx, dy = float(drive_dx), float(drive_dy)
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return _apply_axis_offset(meet, stopper, axis="y", delta=magnitude)
    px, py = -dy / length, dx / length
    candidates = (
        {
            "x": float(meet["x"]) + px * magnitude,
            "y": float(meet["y"]) + py * magnitude,
        },
        {
            "x": float(meet["x"]) - px * magnitude,
            "y": float(meet["y"]) - py * magnitude,
        },
    )
    best = max(candidates, key=lambda c: _distance_to_stopper(c, stopper))
    return _clamp_grid(best)


def pick_nearest_contesting_defender(
    defender_positions: Dict[str, GridCoordDict],
    shooter_pos: GridCoordDict,
    *,
    is_away_offense: bool,
) -> Tuple[bool, Optional[str]]:
    """Nearest defender qualifying for FB contest at shot moment, or uncontested."""
    best_id: Optional[str] = None
    best_dist: Optional[float] = None
    for d_id, pos in defender_positions.items():
        if not fb_defender_contests_shot(pos, shooter_pos, is_away_offense=is_away_offense):
            continue
        dist = _euclid(pos, shooter_pos)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_id = d_id
    return best_id is not None, best_id
