"""Helpers for computing 1–100 position ratings from a player record."""

from __future__ import annotations

from typing import Dict

# Weights for each position. Each sub-dict maps attribute -> weight percentage (0-1).
# All weights must total 1.0 (100%).
POSITION_WEIGHTS: Dict[str, Dict[str, float]] = {
    "PG": {
        "PS": 0.15,
        "BH": 0.30,
        "IQ": 0.25,
        "SH": 0.00,
        "OD": 0.15,
        "AG": 0.15,
        "FT": 0.00,
        "SC": 0.00,
    },
    "SG": {
        "SH": 0.40,
        "OD": 0.30,
        "AG": 0.10,
        "SC": 0.10,
        "PS": 0.05,
        "BH": 0.00,
        "FT": 0.00,
        "IQ": 0.05,
    },
    "SF": {
        "AG": 0.25,
        "ST": 0.25,
        "SC": 0.10,
        "SH": 0.10,
        "ID": 0.10,
        "OD": 0.10,
        "FT": 0.00,
        "IQ": 0.05,
        "PS": 0.00,
        "RB": 0.05,
    },
    "PF": {
        "RB": 0.40,
        "ST": 0.30,
        "IQ": 0.05,
        "SC": 0.05,
        "ID": 0.15,
        "height": 0.05,
        "FT": 0.00,
        "PS": 0.00,
        "SH": 0.00,
    },
    "C": {
        "SC": 0.30,
        "ID": 0.30,
        "height": 0.20,
        "ST": 0.10,
        "RB": 0.10,
        "PS": 0.00,
        "IQ": 0.00,
        "FT": 0.00,
        "AG": 0.00,
    },
}


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


def _clamp(value: float, lower: int = 1, upper: int = 100) -> int:
    """Round and clamp a value to an integer between ``lower`` and ``upper``."""

    return max(lower, min(upper, int(round(value))))


def compute_position_ratings(player: dict) -> Dict[str, int]:
    """Compute 1–100 ratings for each basketball position.

    ``player`` is a mapping containing numeric attributes either at the top
    level or within ``player['attributes']``.
    """

    ratings: Dict[str, int] = {}
    height_rating = _height_to_rating(_get_attr(player, "height"))

    for pos, weights in POSITION_WEIGHTS.items():
        total = 0.0
        for attr, weight in weights.items():
            if attr == "height":
                val = height_rating
            else:
                val = _get_attr(player, attr)
            total += val * weight
        ratings[pos] = _clamp(total)

    return ratings


def add_position_ratings(player: dict) -> dict:
    """Return a shallow copy of ``player`` with computed position ratings."""

    new_player = player.copy()
    new_player["ratings"] = compute_position_ratings(player)
    return new_player


__all__ = ["compute_position_ratings", "add_position_ratings"]
