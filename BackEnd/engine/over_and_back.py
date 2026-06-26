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
