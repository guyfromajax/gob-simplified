"""
Over-and-back pass geometry and passer awareness (universal primitives).

Used by dynamic FCP/HCT pass branches today; intended for HCO and other pass
paths as they adopt the same pre-pass gate.
"""

from __future__ import annotations

import random
from typing import Any, Dict, Optional

OOB_PASS_PS_WEIGHT = 0.8
OOB_PASS_CH_WEIGHT = 0.2

# Non-BH offenders still in backcourt after FC is established sprint toward this
# band (home orientation; flipped for away offense in ``cross_half_urgency_target``).
CROSS_HALF_URGENCY_X_MIN = 51
CROSS_HALF_URGENCY_X_MAX = 57
CROSS_HALF_URGENCY_Y_JITTER = 8


def crossed_half_court(x: float, is_away_offense: bool) -> bool:
    return x <= 50 if is_away_offense else x >= 50


def in_backcourt(x: float, is_away_offense: bool) -> bool:
    """True when ``x`` is behind the half-court line for this offense."""
    return not crossed_half_court(x, is_away_offense)


def is_over_and_back_pass(
    frontcourt_established: bool,
    receiver_xy: Dict[str, Any],
    is_away_offense: bool,
) -> bool:
    """True when a completed pass to ``receiver_xy`` would be an over-and-back."""
    if not frontcourt_established:
        return False
    return in_backcourt(float(receiver_xy.get("x", 50)), is_away_offense)


def passer_over_and_back_threshold(passer: Any) -> float:
    """Awareness floor: ``0.8 × PS + 0.2 × CH`` (passer attributes, 0–100 scale)."""
    attrs = getattr(passer, "attributes", None) or {}
    ps = float(attrs.get("PS", 50) or 50)
    ch = float(attrs.get("CH", 50) or 50)
    return OOB_PASS_PS_WEIGHT * ps + OOB_PASS_CH_WEIGHT * ch


def passer_commits_over_and_back_pass(passer: Any, rng: Any = random) -> bool:
    """Return True if the passer makes the illegal backcourt pass.

    ``roll = randint(1, 100)``. Pass occurs when ``roll > threshold`` — higher
    PS/CH raises the bar (smarter passer holds); lower attributes → more mistakes.
    """
    roll = int(rng.randint(1, 100))
    return roll > passer_over_and_back_threshold(passer)


def cross_half_urgency_target(
    current_xy: Dict[str, Any],
    is_away_offense: bool,
    *,
    clamp_fn,
    flip_fn,
    rng: Any = random,
) -> Dict[str, int]:
    """Random frontcourt-side target for a backcourt offender clearing half court."""
    start_y = int(current_xy.get("y", 25))
    y = start_y + rng.randint(-CROSS_HALF_URGENCY_Y_JITTER, CROSS_HALF_URGENCY_Y_JITTER)
    y = max(5, min(45, y))
    target = {
        "x": rng.randint(CROSS_HALF_URGENCY_X_MIN, CROSS_HALF_URGENCY_X_MAX),
        "y": y,
    }
    if is_away_offense:
        target = flip_fn(target)
    return clamp_fn(target)


def should_hold_instead_of_backcourt_pass(
    frontcourt_established: bool,
    receiver_xy: Dict[str, Any],
    is_away_offense: bool,
    passer: Any,
    grace_bh_pos: Optional[str],
    current_bh_pos: str,
    rng: Any = random,
) -> bool:
    """True when an over-and-back outlet should become a hold beat instead.

    During the one-beat grace for the first BH to establish frontcourt, backward
    passes are always held. After grace, the passer may still throw the pass
    when ``passer_commits_over_and_back_pass`` returns True (PS/CH roll).
    """
    if not is_over_and_back_pass(frontcourt_established, receiver_xy, is_away_offense):
        return False
    if grace_bh_pos is not None and current_bh_pos == grace_bh_pos:
        return True
    return not passer_commits_over_and_back_pass(passer, rng=rng)
