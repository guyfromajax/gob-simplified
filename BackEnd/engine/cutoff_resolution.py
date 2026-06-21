"""
Shared drive-cutoff geometry and defender selection.

Used by HCT broken-trap drives (``dynamic_hct._do_broken_hct_cutoff``) and
Covert Release fast-break defensive stops (``phase_resolution.resolve_fast_break_logic``).
Both share the D21 arrival-time race along the BH's straight-line drive path;
FB passes looser corridor / time-slack tuning for the more open transition floor.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _euclid(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    return math.hypot(float(b["x"]) - float(a["x"]), float(b["y"]) - float(a["y"]))


def _interpolate(start: Dict[str, Any], end: Dict[str, Any], progress: float) -> Dict[str, int]:
    p = max(0.0, min(1.0, progress))
    return {
        "x": int(round(float(start["x"]) + (float(end["x"]) - float(start["x"])) * p)),
        "y": int(round(float(start["y"]) + (float(end["y"]) - float(start["y"])) * p)),
    }


def _perpendicular_distance_to_segment(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> float:
    """Shortest distance from point P to segment AB."""
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def cutoff_meet_point(
    mover_start: Dict[str, Any],
    mover_target: Dict[str, Any],
    mover_rate: float,
    defender_xy: Dict[str, Any],
    defender_rate: float,
    *,
    defender_time_slack: float = 1.0,
    clamp_fn=None,
) -> Optional[Dict[str, int]]:
    """Walk the mover's straight path and return the first point the defender
    can reach no later than the mover (× ``defender_time_slack``)."""
    if mover_rate <= 0 or defender_rate <= 0:
        return None
    total = _euclid(mover_start, mover_target)
    if total <= 0:
        return None
    slack = max(1.0, float(defender_time_slack))
    steps = max(1, int(round(total)))
    for i in range(steps + 1):
        s = i / steps
        point = _interpolate(mover_start, mover_target, s)
        t_mover = (total * s) / mover_rate
        t_def = _euclid(defender_xy, point) / defender_rate
        if t_def <= t_mover * slack:
            raw = {"x": point["x"], "y": point["y"]}
            return clamp_fn(raw) if clamp_fn else raw
    return None


def _meet_progress(
    mover_start: Dict[str, Any],
    meet: Dict[str, Any],
    mover_target: Dict[str, Any],
) -> float:
    path_len = _euclid(mover_start, mover_target)
    return _euclid(mover_start, meet) / path_len if path_len > 0 else 0.0


def best_cutoff_on_drive(
    bh_start: Dict[str, Any],
    target: Dict[str, Any],
    bh_rate: float,
    def_coords: Dict[str, Dict[str, int]],
    def_lineup: Dict[str, Any],
    *,
    get_defender_rate,
    path_corridor: Optional[float] = None,
    defender_time_slack: float = 1.0,
    stop_attempt_prob: Optional[float] = None,
    clamp_fn=None,
    rng=None,
) -> Tuple[Optional[str], Optional[Dict[str, int]]]:
    """Pick the defender with the earliest meet point along the drive path.

    ``get_defender_rate(player)`` returns grid/sec (HCT: AG standard; FB: sprint).
    When ``stop_attempt_prob`` is set (FB aggression gate), each candidate rolls
    before inclusion. ``path_corridor`` skips defenders far from the drive segment.
    """
    if rng is None:
        rng = random
    ax, ay = float(bh_start["x"]), float(bh_start["y"])
    bx, by = float(target["x"]), float(target["y"])

    best_pos: Optional[str] = None
    best_meet: Optional[Dict[str, int]] = None
    best_progress = float("inf")
    best_def_dist = float("inf")

    for pos in POSITIONS:
        defender = def_lineup.get(pos)
        if defender is None or pos not in def_coords:
            continue
        dxy = def_coords[pos]
        if path_corridor is not None:
            dist = _perpendicular_distance_to_segment(
                float(dxy["x"]), float(dxy["y"]), ax, ay, bx, by,
            )
            if dist > path_corridor:
                continue
        if stop_attempt_prob is not None and rng.random() >= stop_attempt_prob:
            continue
        def_rate = get_defender_rate(defender)
        meet = cutoff_meet_point(
            bh_start, target, bh_rate, dxy, def_rate,
            defender_time_slack=defender_time_slack,
            clamp_fn=clamp_fn,
        )
        if meet is None:
            continue
        progress = _meet_progress(bh_start, meet, target)
        def_dist = _euclid(dxy, meet)
        if progress < best_progress or (
            abs(progress - best_progress) < 1e-6 and def_dist < best_def_dist
        ):
            best_progress = progress
            best_def_dist = def_dist
            best_pos = pos
            best_meet = meet
    return best_pos, best_meet


def resolve_cutoff_contest(
    off_team,
    def_team,
    ball_handler,
    cutoff_defender,
    *,
    exclude_steal: bool = True,
) -> Tuple[str, float, Any]:
    """D8 moment resolution at a drive meet point (lazy import avoids cycles)."""
    from BackEnd.engine.dynamic_hct import _resolve_moment

    return _resolve_moment(
        off_team, def_team, ball_handler, cutoff_defender,
        None, exclude_steal=exclude_steal,
    )


def map_cutoff_outcome_to_fb(outcome: str) -> Tuple[str, Dict[str, Any]]:
    """Map a D8 cutoff outcome to a Fast Break ``event_type`` + fb_roles flags."""
    if outcome == "POS_O":
        return "SHOT", {"ball_handler_beats_defender": True}
    if outcome == "NEUTRAL":
        return "DEFENSIVE_STOP", {}
    if outcome == "D_FOUL":
        return "FOUL", {"foul_team": "DEFENSE", "foul_player": None}
    if outcome == "O_FOUL":
        return "FOUL", {"foul_team": "OFFENSE", "foul_player": None}
    if outcome == "DEAD BALL":
        return "DEAD BALL", {}
    return "DEFENSIVE_STOP", {}
