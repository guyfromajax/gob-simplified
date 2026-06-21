"""Shot-location geometry helpers.

The court engine stores HCO spot constants in home-offense orientation:
home offense attacks the right/home rim, and away offense mirrors x.
"""

from __future__ import annotations

from typing import Mapping


_THREE_POINT_ARC_HOME = (
    {"x": 88.0, "y": 6.0},
    {"x": 81.0, "y": 7.0},
    {"x": 73.0, "y": 10.0},
    {"x": 68.0, "y": 14.0},
    {"x": 64.0, "y": 25.0},
    {"x": 68.0, "y": 36.0},
    {"x": 73.0, "y": 40.0},
    {"x": 81.0, "y": 43.0},
    {"x": 88.0, "y": 44.0},
)


def is_three_point_shot_from_coords(
    coords: Mapping[str, float] | None,
    *,
    is_away_offense: bool,
) -> bool:
    """Return True when ``coords`` are behind the 3-point arc.

    ``coords`` must be in display-oriented court coordinates. Away offense is
    mirrored into the same home-offense geometry before the arc test.
    """

    if not isinstance(coords, Mapping):
        return False
    try:
        x = float(coords["x"])
        y = float(coords["y"])
    except (KeyError, TypeError, ValueError):
        return False

    normalized_x = 100.0 - x if is_away_offense else x
    normalized_y = y

    points = _THREE_POINT_ARC_HOME
    if normalized_y <= points[0]["y"]:
        return normalized_x <= points[0]["x"]
    if normalized_y >= points[-1]["y"]:
        return normalized_x <= points[-1]["x"]

    for lower, upper in zip(points, points[1:]):
        if lower["y"] <= normalized_y <= upper["y"]:
            span = upper["y"] - lower["y"]
            if abs(span) < 1e-9:
                boundary_x = min(lower["x"], upper["x"])
            else:
                t = (normalized_y - lower["y"]) / span
                boundary_x = lower["x"] + t * (upper["x"] - lower["x"])
            return normalized_x <= boundary_x

    return False
