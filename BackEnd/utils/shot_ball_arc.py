"""Backend-authored shot ball-arc geometry for schema [ball_flight] steps.

FE is a pure renderer: reads ``advance_trigger.metadata.shot_ball_arc`` and
tweens the ball along a distance-scaled, skewed parabola. Non-arc shots omit
the field and keep the existing straight-line flight.
"""

from __future__ import annotations

from BackEnd.utils.sim_random import sim_rng as random
from typing import Any, Dict, Optional

from BackEnd.constants import (
    ARC_SHOT_BALL_GRID_PER_GAME_SECOND,
    AWAY_RIM_COORDS,
    HOME_RIM_COORDS,
    SHOT_BALL_GRID_PER_GAME_SECOND,
)
from BackEnd.constants.shot_micro_movements_constants import (
    APEX_BIAS,
    APEX_HEIGHT_REF,
    ARC_BASE,
    ARC_SLOPE,
    SHOT_ARC_FAMILY_STYLE,
    SHOT_ARC_PROBABILITY,
    SHOT_ARC_STYLE_MULT,
)
from BackEnd.utils.animation_step_schema import GridCoord
from BackEnd.utils.animation_step_helpers import _euclid


def _attacking_rim(away_offense: bool) -> GridCoord:
    return dict(AWAY_RIM_COORDS if away_offense else HOME_RIM_COORDS)


def roll_shot_arc(family_id: str) -> bool:
    """Roll whether this shot attempt uses arced [ball_flight] (replay uses global RNG)."""
    prob = SHOT_ARC_PROBABILITY.get(family_id)
    if prob is None:
        return False
    if prob >= 1.0:
        return True
    if prob <= 0.0:
        return False
    return random.random() < prob


def shot_ball_flight_grid_rate(*, uses_arc: bool) -> float:
    """Grid/game-sec rate for schema [ball_flight] (straight vs arc)."""
    if uses_arc:
        return float(ARC_SHOT_BALL_GRID_PER_GAME_SECOND)
    return float(SHOT_BALL_GRID_PER_GAME_SECOND)


def compute_shot_ball_arc(
    release_coord: GridCoord,
    *,
    away_offense: bool,
    family_id: str,
) -> Optional[Dict[str, float]]:
    """Return arc descriptor for FE, or None when family has no arc style."""
    style = SHOT_ARC_FAMILY_STYLE.get(family_id)
    if not style:
        return None
    style_mult = SHOT_ARC_STYLE_MULT.get(style, 1.0)
    rim = _attacking_rim(away_offense)
    dist_grid = _euclid(release_coord, rim)
    apex_px = (ARC_BASE + ARC_SLOPE * dist_grid) * style_mult
    flatness = min(1.0, apex_px / APEX_HEIGHT_REF)
    apex_pos = max(0.50, min(0.60, APEX_BIAS + 0.06 * (1.0 - flatness)))
    return {
        "apex_px": float(apex_px),
        "apex_pos": float(apex_pos),
        "dist_grid": float(dist_grid),
        "style": style,
    }


def stamp_shot_ball_arc_metadata(
    metadata: Dict[str, Any],
    turn_result: Dict[str, Any],
    release_coord: GridCoord,
    away_offense: bool,
) -> None:
    """Attach ``shot_ball_arc`` to [ball_flight] trigger metadata when applicable."""
    result_type = (turn_result.get("result_type") or "").upper()
    if result_type == "BLOCK":
        return
    if not turn_result.get("uses_shot_arc"):
        return
    family_id = turn_result.get("micro_movement_family")
    if not family_id:
        return
    arc = compute_shot_ball_arc(
        release_coord,
        away_offense=away_offense,
        family_id=str(family_id),
    )
    if arc:
        metadata["shot_ball_arc"] = arc
        metadata["ball_grid_per_game_second"] = float(ARC_SHOT_BALL_GRID_PER_GAME_SECOND)
