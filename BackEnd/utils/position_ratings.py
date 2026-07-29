"""Helpers for computing position ratings from a player record.

Position rating (RT) model — Player Attribute Recalibration, design §3.6:

    RT_pos = attribute_weighted_mean(pos) × height_fitness(pos, height)

Height is a **multiplier**, not a weighted term. This lets height *gate* a
position (a short player cannot rate as a centre) rather than merely forgoing a
few points, which is what additive height weights allowed. Every position
carries a fitness curve — gating only PF/C leaves guards ungated at every height
and collapses centre supply (design §3.6.2).

There is ONE weight table and ONE height-fitness table for everyone. The old
recruit-specific tables and the ``profile`` parameter are gone: a player's RT
must not change at signing without development having occurred (design §3.3).
"""

from __future__ import annotations

from typing import Dict

# Attribute weights per position (design §3.6.1). Each sub-dict maps
# attribute -> weight; each table sums to 1.0, so the weighted sum is a mean.
# Height is intentionally absent — it enters multiplicatively below.
POSITION_WEIGHTS: Dict[str, Dict[str, float]] = {
    "PG": {"BH": 0.30, "IQ": 0.25, "PS": 0.15, "OD": 0.10, "AG": 0.10, "SH": 0.05, "FT": 0.05},
    "SG": {"SH": 0.42, "OD": 0.25, "SC": 0.11, "AG": 0.07, "PS": 0.05, "IQ": 0.05, "FT": 0.05},
    "SF": {"AG": 0.22, "OD": 0.20, "SC": 0.18, "ID": 0.16, "SH": 0.14, "RB": 0.05, "FT": 0.05},
    "PF": {"RB": 0.30, "ST": 0.22, "AG": 0.16, "SH": 0.14, "SC": 0.08, "IQ": 0.05, "FT": 0.05},
    "C":  {"ID": 0.32, "RB": 0.22, "ST": 0.20, "SC": 0.18, "IQ": 0.04, "FT": 0.04},
}

# Multiplicative, piecewise-linear height fitness (design §3.6.2). Peaks at
# ``ideal`` (fitness 1.0) and falls off by an asymmetric per-inch penalty,
# clamped to [HEIGHT_FITNESS_FLOOR, HEIGHT_FITNESS_CAP]. The asymmetry is what
# separates neighbouring positions structurally: PG falls off fast when tall,
# C falls off slowly when tall but fast when short.
HEIGHT_FITNESS_FLOOR = 0.50
HEIGHT_FITNESS_CAP = 1.15

# (ideal_in, short_penalty_per_inch, tall_penalty_per_inch)
HEIGHT_FITNESS: Dict[str, tuple[float, float, float]] = {
    "PG": (73.5, 0.020, 0.050),
    "SG": (76.0, 0.030, 0.045),
    "SF": (78.5, 0.035, 0.035),
    "PF": (80.5, 0.050, 0.025),
    "C":  (82.5, 0.060, 0.010),
}


def _get_attr(player: dict, key: str) -> float:
    """Retrieve an attribute value from a player dict.

    Looks first under ``player['attributes']`` then falls back to the top level.
    Missing keys default to ``0``.
    """

    attributes = player.get("attributes", {}) or {}
    return attributes.get(key, player.get(key, 0))


def _height_inches(player: dict) -> float:
    try:
        return float(_get_attr(player, "height"))
    except (TypeError, ValueError):
        return 0.0


def height_fitness(position: str, height: float) -> float:
    """Multiplicative height fitness for ``position`` at ``height`` inches.

    Peaks at the position's ideal height and declines by an asymmetric per-inch
    penalty, clamped to [0.50, 1.15]. See design §3.6.2.
    """

    ideal, short_penalty, tall_penalty = HEIGHT_FITNESS[position]
    try:
        h = float(height)
    except (TypeError, ValueError):
        h = 0.0
    if h <= 0:
        return HEIGHT_FITNESS_FLOOR
    if h < ideal:
        raw = 1.0 - short_penalty * (ideal - h)
    else:
        raw = 1.0 - tall_penalty * (h - ideal)
    return max(HEIGHT_FITNESS_FLOOR, min(HEIGHT_FITNESS_CAP, raw))


def _clamp(value: float, lower: int = 1, upper: int | None = 100) -> int:
    """Round and clamp a value to an integer with a lower bound and optional upper bound."""

    rounded = int(round(value))
    if upper is None:
        return max(lower, rounded)
    return max(lower, min(upper, rounded))


def compute_position_ratings(player: dict) -> Dict[str, int]:
    """Compute a rating for each basketball position.

    ``player`` is a mapping containing numeric attributes either at the top
    level or within ``player['attributes']``, plus a ``height`` in inches.

    RT = weighted attribute mean × height fitness, clamped at a lower bound of 1
    and uncapped above (a few players legitimately exceed 100; see design §4.3).
    """

    ratings: Dict[str, int] = {}
    height = _height_inches(player)
    for pos, weights in POSITION_WEIGHTS.items():
        attribute_mean = 0.0
        for attr, weight in weights.items():
            attribute_mean += _get_attr(player, attr) * weight
        ratings[pos] = _clamp(attribute_mean * height_fitness(pos, height), lower=1, upper=None)
    return ratings


def add_position_ratings(player: dict) -> dict:
    """Return a shallow copy of ``player`` with computed position ratings."""

    new_player = player.copy()
    new_player["ratings"] = compute_position_ratings(player)
    return new_player


__all__ = [
    "POSITION_WEIGHTS",
    "HEIGHT_FITNESS",
    "HEIGHT_FITNESS_FLOOR",
    "HEIGHT_FITNESS_CAP",
    "height_fitness",
    "compute_position_ratings",
    "add_position_ratings",
]
