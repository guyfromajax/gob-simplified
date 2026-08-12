"""Universal make/miss reconciliation for uncontested inside and attack shots.

See Shot_System.md § Uncontested inside/attack make rule.
"""
from __future__ import annotations

import math
from BackEnd.utils.sim_random import sim_rng as random
from BackEnd.utils.team_attr_scale import core8_gameplay
from typing import Any, Optional

# Matches CONTEST_EUCLIDEAN_RADIUS — uncontested helper geo gate.
UNCONTESTED_INSIDE_ATTACK_MAX_DIST = 11.0
UNCONTESTED_MAKE_THRESHOLD_BASE = 99.0


def _team_attr(team: Any, key: str, default: float = 0.0) -> float:
    return float((getattr(team, "team_attributes", None) or {}).get(key, default) or 0)


def uncontested_inside_attack_distance(
    shooter_x: float,
    shooter_y: float,
    basket_x: float,
    basket_y: float,
) -> float:
    return math.hypot(float(shooter_x) - float(basket_x), float(shooter_y) - float(basket_y))


def uncontested_inside_attack_helper_eligible(
    *,
    shot_type: str,
    shooter_x: float,
    shooter_y: float,
    basket_x: float,
    basket_y: float,
    is_three: bool = False,
) -> bool:
    """True when the universal uncontested roll helper may run (type + geo)."""
    if is_three or str(shot_type or "").lower() not in ("inside", "attack"):
        return False
    dist = uncontested_inside_attack_distance(shooter_x, shooter_y, basket_x, basket_y)
    return dist <= UNCONTESTED_INSIDE_ATTACK_MAX_DIST


def compute_uncontested_inside_attack_make_threshold(
    *,
    shooter_x: float,
    shooter_y: float,
    basket_x: float,
    basket_y: float,
    off_team: Any,
    def_team: Any,
) -> Optional[float]:
    """Return the make threshold, or None when geo/type excludes the helper."""
    dist = uncontested_inside_attack_distance(shooter_x, shooter_y, basket_x, basket_y)
    if dist > UNCONTESTED_INSIDE_ATTACK_MAX_DIST:
        return None
    # THE RULE: core-8 attrs (discipline, fight) feed gameplay through core8_gameplay()
    # so the ±20 stored range plays as the calibrated ±10 swing (floor 79, not 59).
    threshold = (
        UNCONTESTED_MAKE_THRESHOLD_BASE
        + core8_gameplay(_team_attr(off_team, "discipline"))
        - core8_gameplay(_team_attr(def_team, "fight"))
    )
    if dist >= 12:
        threshold -= 2.0 * (dist - 11.0)
    return max(1.0, min(100.0, threshold))


def resolve_uncontested_inside_attack_make(
    *,
    shot_type: str,
    shooter_x: float,
    shooter_y: float,
    basket_x: float,
    basket_y: float,
    off_team: Any,
    def_team: Any,
    is_three: bool = False,
) -> Optional[bool]:
    """Roll-based make/miss for uncontested inside/attack within geo range.

    Returns ``None`` when the helper does not apply (outside/three, or distance
    > ``UNCONTESTED_INSIDE_ATTACK_MAX_DIST``). Otherwise ``True`` = make.
    """
    if not uncontested_inside_attack_helper_eligible(
        shot_type=shot_type,
        shooter_x=shooter_x,
        shooter_y=shooter_y,
        basket_x=basket_x,
        basket_y=basket_y,
        is_three=is_three,
    ):
        return None
    threshold = compute_uncontested_inside_attack_make_threshold(
        shooter_x=shooter_x,
        shooter_y=shooter_y,
        basket_x=basket_x,
        basket_y=basket_y,
        off_team=off_team,
        def_team=def_team,
    )
    if threshold is None:
        return None
    roll = random.randint(1, 100)
    return roll < threshold


def apply_uncontested_inside_attack_make(
    *,
    shot_type: str,
    shooter_x: float,
    shooter_y: float,
    basket_x: float,
    basket_y: float,
    off_team: Any,
    def_team: Any,
    is_three: bool = False,
    shot_score: Optional[float] = None,
    shot_threshold: Optional[float] = None,
) -> bool:
    """Helper make roll when eligible; else ``shot_score >= shot_threshold`` fallback."""
    helper_make = resolve_uncontested_inside_attack_make(
        shot_type=shot_type,
        shooter_x=shooter_x,
        shooter_y=shooter_y,
        basket_x=basket_x,
        basket_y=basket_y,
        off_team=off_team,
        def_team=def_team,
        is_three=is_three,
    )
    if helper_make is not None:
        return helper_make
    if shot_score is not None and shot_threshold is not None:
        return float(shot_score) >= float(shot_threshold)
    return True
