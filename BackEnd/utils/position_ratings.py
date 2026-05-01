"""Helpers for computing position ratings from a player record."""

from __future__ import annotations

from typing import Dict, Literal

# Weights for each position. Each sub-dict maps attribute -> weight percentage (0-1).
# All weights must total 1.0 (100%).
POSITION_WEIGHTS: Dict[str, Dict[str, float]] = {
    "PG": {
        "PS": 0.15,
        "BH": 0.30,
        "IQ": 0.25,
        "SH": 0.05,
        "OD": 0.10,
        "AG": 0.10,
        "FT": 0.05,
        "SC": 0.00,
    },
    "SG": {
        "SH": 0.40,
        "OD": 0.25,
        "AG": 0.10,
        "SC": 0.10,
        "PS": 0.05,
        "BH": 0.00,
        "FT": 0.05,
        "IQ": 0.05,
    },
    "SF": {
        "AG": 0.25,
        "ST": 0.25,
        "SC": 0.10,
        "SH": 0.10,
        "ID": 0.10,
        "OD": 0.10,
        "FT": 0.05,
        "IQ": 0.05,
        "PS": 0.00,
        "RB": 0.00,
    },
    "PF": {
        "RB": 0.25,
        "ST": 0.25,
        "IQ": 0.05,
        "SC": 0.05,
        "ID": 0.15,
        "height": 0.20,
        "FT": 0.05,
        "PS": 0.00,
        "SH": 0.00,
    },
    "C": {
        "SC": 0.15,
        "ID": 0.15,
        "height": 0.40,
        "ST": 0.15,
        "RB": 0.15,
        "PS": 0.00,
        "IQ": 0.00,
        "FT": 0.00,
        "AG": 0.00,
    },
}

RECRUIT_POSITION_WEIGHTS: Dict[str, Dict[str, float]] = {
    **POSITION_WEIGHTS,
    "PF": {
        "RB": 0.30,
        "ST": 0.30,
        "IQ": 0.05,
        "SC": 0.05,
        "ID": 0.15,
        "height": 0.10,
        "FT": 0.05,
        "PS": 0.00,
        "SH": 0.00,
    },
    "C": {
        "SC": 0.30,
        "ID": 0.30,
        "height": 0.10,
        "ST": 0.15,
        "RB": 0.15,
        "PS": 0.00,
        "IQ": 0.00,
        "FT": 0.00,
        "AG": 0.00,
    },
}

PositionRatingProfile = Literal["player", "recruit"]


def _get_attr(player: dict, key: str) -> float:
    """Retrieve an attribute value from a player dict.

    Looks first under ``player['attributes']`` then falls back to the top level.
    Missing keys default to ``0``.
    """

    attributes = player.get("attributes", {}) or {}
    return attributes.get(key, player.get(key, 0))


def _height_to_rating(height: float) -> float:
    """Convert a height in inches to a 1–100 rating.

    Uses a linear map where 60 inches -> 1 and 84 inches -> 100 and clamps
    outside that range.
    """

    try:
        h = float(height)
    except (TypeError, ValueError):
        h = 0

    if h <= 60:
        return 1.0
    if h >= 84:
        return 100.0
    # scale proportionally between 60 and 84 inclusive
    return 1 + (h - 60) * (99 / 24)


def _clamp(value: float, lower: int = 1, upper: int | None = 100) -> int:
    """Round and clamp a value to an integer with a lower bound and optional upper bound."""

    rounded = int(round(value))
    if upper is None:
        return max(lower, rounded)
    return max(lower, min(upper, rounded))


def compute_position_ratings(player: dict, profile: PositionRatingProfile = "player") -> Dict[str, int]:
    """Compute position ratings for each basketball position.

    ``player`` is a mapping containing numeric attributes either at the top
    level or within ``player['attributes']``.
    """

    ratings: Dict[str, int] = {}
    height_rating = _height_to_rating(_get_attr(player, "height"))
    position_weights = RECRUIT_POSITION_WEIGHTS if profile == "recruit" else POSITION_WEIGHTS

    for pos, weights in position_weights.items():
        total = 0.0
        for attr, weight in weights.items():
            if attr == "height":
                val = height_rating
            else:
                val = _get_attr(player, attr)
            total += val * weight
        ratings[pos] = _clamp(total, lower=1, upper=None)

    return ratings


def add_position_ratings(player: dict) -> dict:
    """Return a shallow copy of ``player`` with computed position ratings."""

    new_player = player.copy()
    new_player["ratings"] = compute_position_ratings(player)
    return new_player


__all__ = ["compute_position_ratings", "add_position_ratings"]
