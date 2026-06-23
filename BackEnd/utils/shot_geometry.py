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


def _normalize_shot_coords(
    coords: Mapping[str, float] | None,
    *,
    is_away_offense: bool,
) -> tuple[dict[str, float], dict[str, float]] | None:
    if not isinstance(coords, Mapping):
        return None
    try:
        x = float(coords["x"])
        y = float(coords["y"])
    except (KeyError, TypeError, ValueError):
        return None

    normalized_x = 100.0 - x if is_away_offense else x
    normalized_y = y
    return (
        {"x": x, "y": y},
        {"x": normalized_x, "y": normalized_y},
    )


def _three_point_boundary_x(normalized_y: float) -> float | None:
    points = _THREE_POINT_ARC_HOME
    if normalized_y <= points[0]["y"]:
        return points[0]["x"]
    if normalized_y >= points[-1]["y"]:
        return points[-1]["x"]

    for lower, upper in zip(points, points[1:]):
        if lower["y"] <= normalized_y <= upper["y"]:
            span = upper["y"] - lower["y"]
            if abs(span) < 1e-9:
                return min(lower["x"], upper["x"])
            t = (normalized_y - lower["y"]) / span
            return lower["x"] + t * (upper["x"] - lower["x"])

    return None


def is_three_point_shot_from_coords(
    coords: Mapping[str, float] | None,
    *,
    is_away_offense: bool,
) -> bool:
    """Return True when ``coords`` are behind the 3-point arc.

    ``coords`` must be in display-oriented court coordinates. Away offense is
    mirrored into the same home-offense geometry before the arc test.
    """

    normalized = _normalize_shot_coords(coords, is_away_offense=is_away_offense)
    if normalized is None:
        return False
    _display_coord, normalized_coord = normalized
    boundary_x = _three_point_boundary_x(normalized_coord["y"])
    if boundary_x is None:
        return False
    return normalized_coord["x"] <= boundary_x


def classify_shot_value(
    coords: Mapping[str, float] | None,
    *,
    is_away_offense: bool,
    allow_three: bool = True,
    forced_points: int | None = None,
    classification_source: str = "coords",
) -> dict:
    """Classify a shot's value from backend-owned shot coordinates.

    Field-goal callers normally pass display-oriented ``coords`` and let the
    helper decide between 2 and 3. Paths that bypass geometry, such as free
    throws or forced-at-rim attempts, pass ``forced_points`` so downstream code
    still receives a self-describing classification payload.
    """

    if forced_points is not None:
        points = int(forced_points)
        return {
            "points": points,
            "shot_value": points,
            "is_three_point_shot": False,
            "classification_coord": None,
            "normalized_coord": None,
            "boundary_x": None,
            "classification_source": "forced_one" if points == 1 else "forced_two",
            "allow_three": False,
        }

    normalized = _normalize_shot_coords(coords, is_away_offense=is_away_offense)
    if normalized is None:
        return {
            "points": 2,
            "shot_value": 2,
            "is_three_point_shot": False,
            "classification_coord": None,
            "normalized_coord": None,
            "boundary_x": None,
            "classification_source": "missing_coords",
            "allow_three": bool(allow_three),
        }

    display_coord, normalized_coord = normalized
    boundary_x = _three_point_boundary_x(normalized_coord["y"])
    is_three = bool(
        allow_three
        and boundary_x is not None
        and normalized_coord["x"] <= boundary_x
    )
    points = 3 if is_three else 2
    source = classification_source if allow_three else "forced_two"
    return {
        "points": points,
        "shot_value": points,
        "is_three_point_shot": is_three,
        "classification_coord": display_coord,
        "normalized_coord": normalized_coord,
        "boundary_x": boundary_x,
        "classification_source": source,
        "allow_three": bool(allow_three),
    }
