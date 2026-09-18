"""Where a zone defender stands when his area is empty (rung (e)).

Replaces ``_find_closest_spot_in_zone_to_point``, which snapped the defender to
whichever LISTED SPOT was nearest the ball. That gave each defender an effective
menu of 2-6 discrete positions - the 2-3 power forward stood on one spot 87% of the
time, and six of the fifteen defenders parked in ``midLane`` - and it read nothing
about the ball beyond "which of my spots is closest". See
``reports/zone-empty-branch-2026-09-18.md``.

The model, in one line::

    position = clamp(anchor + pull_toward_ball + pull_toward_basket)

**Anchor.** The zone's *pole of inaccessibility*: the interior point furthest from
any edge. Used rather than a centroid because several rings are concave, and a
centroid can fall outside a concave polygon - the pole cannot, by construction.
Zones are static data, so every anchor is computed once at import
(``warm_anchor_cache``) and never per step.

**Primary term: ball distance and side.** How far the ball is from the defender's
area, and whether he is strong side or weak side, is the leading term. A weak-side
defender sinks toward the rim; a strong-side defender shades toward the ball.
``strongness`` is continuous rather than a binary side flag so that a defender
anchored near the midline does not flip between two positions as the ball crosses.

**Secondary term: role class**, derived from each zone's own geometry - the
anchor's distance to the rim - and never hand-authored per zone. The class sets
``reach``: how far from his anchor the defender may move at all. There are no
per-zone constants anywhere in this module; 55 hand-set pairs would not be
maintainable.

**Clamp.** v1 keeps the defender inside his own polygon: he does not leave his area
to help. That is deliberate, and it is what makes man-vs-zone a legible trade-off -
man gives real help rotations, zone gives shape.

**IQ is calibration, not magnitude.** A low-IQ defender is pulled *too far toward
the ball*, off the correct spot; a high-IQ defender holds the balance. The error is
directional, and it is rolled ONCE PER DEFENDER PER ZONE POSSESSION, not per step -
a defender either has his attention for that trip down the floor or he does not.
Per-step rolls would be ~11,200 draws a game. The hook is wired here but
``iq_error`` is supplied by the caller; with no error supplied this module draws
nothing at all.

Everything is behind ``GOB_ZONE_SINK``, default OFF.
"""

from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Sequence, Tuple

Point = Tuple[float, float]

# ---------------------------------------------------------------- tunables ----

# Role class thresholds, in grid units of anchor-to-rim distance. Picked from the
# measured distribution over all 55 repaired zones (quartiles 7.7 / 13.6 / 16.0 /
# 20.0 / 22.9), not chosen a priori.
INTERIOR_RIM_DISTANCE = 12.0      # anchor closer than this to the rim -> "interior"
PERIMETER_RIM_DISTANCE = 20.0     # anchor further than this -> "perimeter"

# How far the ball can be, in y, before a defender counts as fully weak side.
SIDE_SPAN = 30.0

# Ball centrality: with the ball in the middle of the floor there is no weak side,
# so every defender is treated as strong side. Full effect inside the plateau,
# ramping LINEARLY to zero at the outer bounds - a hard edge would make defenders
# snap as the ball drifted across the boundary, which is the exact discontinuity
# this whole model exists to remove.
CENTRALITY_PLATEAU = (23.0, 28.0)
CENTRALITY_OUTER = (18.0, 33.0)

WEIGHT_PRESETS: Dict[str, Dict[str, float]] = {
    # reach_*  : how far (grid units) a defender of that class may leave his anchor
    # ball_*   : fraction of the anchor->ball distance pulled, strong / weak side
    # basket_* : fraction of the anchor->rim  distance pulled, strong / weak side
    "anchored": {
        "reach_perimeter": 4.0, "reach_spanning": 3.0, "reach_interior": 2.0,
        "ball_strong": 0.12, "ball_weak": 0.04,
        "basket_strong": 0.10, "basket_weak": 0.30,
    },
    "balanced": {
        "reach_perimeter": 8.0, "reach_spanning": 6.0, "reach_interior": 4.0,
        "ball_strong": 0.25, "ball_weak": 0.08,
        "basket_strong": 0.15, "basket_weak": 0.50,
    },
    "ball_hungry": {
        "reach_perimeter": 12.0, "reach_spanning": 9.0, "reach_interior": 6.0,
        "ball_strong": 0.45, "ball_weak": 0.15,
        "basket_strong": 0.10, "basket_weak": 0.45,
    },
    "rim_heavy": {
        "reach_perimeter": 8.0, "reach_spanning": 7.0, "reach_interior": 5.0,
        "ball_strong": 0.15, "ball_weak": 0.05,
        "basket_strong": 0.35, "basket_weak": 0.75,
    },
    # The chosen one. Strong side and the middle shade toward the ball moderately
    # (the `balanced` strong-side pair); the weak side is RIM HUNGRY - it sinks hard
    # to the basket rather than chasing across the floor (the `rim_heavy` weak-side
    # pair and reaches). A ball-hungry weak side was considered and rejected.
    "shape": {
        "reach_perimeter": 8.0, "reach_spanning": 7.0, "reach_interior": 5.0,
        "ball_strong": 0.25, "ball_weak": 0.05,
        "basket_strong": 0.15, "basket_weak": 0.75,
    },
}
DEFAULT_PRESET = "shape"


def enabled() -> bool:
    """``GOB_ZONE_SINK`` - default OFF. Read per call so tests can flip it."""
    return os.environ.get("GOB_ZONE_SINK", "0") == "1"


def active_weights() -> Dict[str, float]:
    name = os.environ.get("GOB_ZONE_SINK_WEIGHTS", DEFAULT_PRESET)
    return WEIGHT_PRESETS.get(name, WEIGHT_PRESETS[DEFAULT_PRESET])


# ------------------------------------------------------------ the geometry ----

def _point_to_segment(px: float, py: float, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _inside(px: float, py: float, ring: Sequence[Point]) -> bool:
    # Imported lazily: shared_defense imports this module, so a module-level import
    # of shared_defense here would be circular.
    from BackEnd.utils.shared_defense import _point_in_polygon
    return _point_in_polygon(px, py, ring)


def _signed_clearance(px: float, py: float, ring: Sequence[Point]) -> float:
    d = min(_point_to_segment(px, py, ring[i], ring[(i + 1) % len(ring)])
            for i in range(len(ring)))
    return d if _inside(px, py, ring) else -d


def pole_of_inaccessibility(ring: Sequence[Point], precision: float = 0.05) -> Tuple[Point, float]:
    """The interior point furthest from any edge, plus that clearance.

    Coarse grid sweep then local refinement. Only ever run at import (55 rings), so
    the cost does not matter; correctness on concave rings does.
    """
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    step = max(x1 - x0, y1 - y0) / 24.0 or 1.0

    best = (-math.inf, (x0 + x1) / 2.0, (y0 + y1) / 2.0)
    x = x0
    while x <= x1 + 1e-9:
        y = y0
        while y <= y1 + 1e-9:
            d = _signed_clearance(x, y, ring)
            if d > best[0]:
                best = (d, x, y)
            y += step
        x += step

    while step > precision:
        step /= 2.0
        _, bx, by = best
        for dx in (-step, 0.0, step):
            for dy in (-step, 0.0, step):
                d = _signed_clearance(bx + dx, by + dy, ring)
                if d > best[0]:
                    best = (d, bx + dx, by + dy)
    return (round(best[1], 3), round(best[2], 3)), round(best[0], 3)


def ball_centrality(ball_y: float) -> float:
    """1.0 with the ball in the middle of the floor, 0.0 out at either sideline.

    Linear ramp, never a step: 0 at ``CENTRALITY_OUTER[0]``, rising to 1 across the
    lower shoulder, flat through the plateau, falling back to 0 at
    ``CENTRALITY_OUTER[1]``. Continuous everywhere, so a defender's position moves
    smoothly as the ball drifts across the band rather than snapping at an edge.
    """
    lo_out, hi_out = CENTRALITY_OUTER
    lo_in, hi_in = CENTRALITY_PLATEAU
    if ball_y <= lo_out or ball_y >= hi_out:
        return 0.0
    if lo_in <= ball_y <= hi_in:
        return 1.0
    if ball_y < lo_in:
        return (ball_y - lo_out) / (lo_in - lo_out)
    return (hi_out - ball_y) / (hi_out - hi_in)


def role_class(anchor: Point, rim: Point) -> str:
    """perimeter / spanning / interior, from the anchor's distance to the rim alone."""
    d = math.dist(anchor, rim)
    if d < INTERIOR_RIM_DISTANCE:
        return "interior"
    if d >= PERIMETER_RIM_DISTANCE:
        return "perimeter"
    return "spanning"


# ------------------------------------------------------------- anchor cache ----

_ANCHORS: Dict[Tuple[Point, ...], Tuple[Point, float]] = {}


def anchor_for(ring: Sequence[Point]) -> Tuple[Point, float]:
    """Cached anchor + clearance. Warmed at import; falls back to computing on a
    miss so a ring built at runtime still works."""
    key = tuple(ring)
    hit = _ANCHORS.get(key)
    if hit is None:
        hit = pole_of_inaccessibility(ring)
        _ANCHORS[key] = hit
    return hit


def warm_anchor_cache(tables: Sequence[Dict[str, List[Point]]]) -> int:
    """Precompute one anchor per defender per shift table. Called at import."""
    for table in tables:
        for ring in table.values():
            if len(set(ring)) >= 3:
                anchor_for(ring)
    return len(_ANCHORS)


# ---------------------------------------------------------------- the model ----

def _clamp_into(anchor: Point, target: Point, ring: Sequence[Point]) -> Point:
    """Walk back from ``target`` toward ``anchor`` until inside the polygon.

    The anchor is inside by construction, so this always terminates with a point in
    the defender's own area - that is the v1 "he does not leave his zone" rule.
    """
    if _inside(target[0], target[1], ring):
        return target
    lo, hi = 0.0, 1.0
    for _ in range(24):
        mid = (lo + hi) / 2.0
        p = (anchor[0] + (target[0] - anchor[0]) * mid,
             anchor[1] + (target[1] - anchor[1]) * mid)
        if _inside(p[0], p[1], ring):
            lo = mid
        else:
            hi = mid
    return (anchor[0] + (target[0] - anchor[0]) * lo,
            anchor[1] + (target[1] - anchor[1]) * lo)


def sink_position(
    ring: Sequence[Point],
    ball: Point,
    rim: Point,
    weights: Optional[Dict[str, float]] = None,
    iq_error: float = 0.0,
) -> Dict[str, float]:
    """Where an empty-zone defender stands.

    ``iq_error`` is the directional calibration error: positive pulls him further
    toward the ball than he should be and slackens his help toward the rim. 0.0 is
    a perfectly calibrated defender, and is the Stage A value. This function draws
    no randomness; the caller rolls the error once per defender per possession.
    """
    w = weights or active_weights()
    anchor, _clearance = anchor_for(ring)
    cls = role_class(anchor, rim)
    reach = w[f"reach_{cls}"]

    d_ball = math.dist(anchor, ball)
    d_rim = math.dist(anchor, rim)

    # Continuous strong-side measure: 1 when the ball is at the defender's own y,
    # 0 when it is a full court-width away across the floor. Side is taken from the
    # ANCHOR, never from the defender's live position - his live position is the
    # output of this function, so reading it would make the model self-referential
    # and path-dependent across steps.
    strongness = 1.0 - min(1.0, abs(ball[1] - anchor[1]) / SIDE_SPAN)

    # With the ball in the middle there is no weak side: push strongness toward 1
    # in proportion to centrality. Composed with the term above rather than
    # replacing it, so off-centre geometry still shows through a partial ramp.
    centrality = ball_centrality(ball[1])
    strongness += (1.0 - strongness) * centrality

    w_ball = w["ball_weak"] + (w["ball_strong"] - w["ball_weak"]) * strongness
    w_basket = w["basket_weak"] + (w["basket_strong"] - w["basket_weak"]) * strongness

    # IQ: over-committing to the ball is the failure mode, and it costs help.
    w_ball *= (1.0 + iq_error)
    w_basket *= max(0.0, 1.0 - iq_error)

    dx = dy = 0.0
    if d_ball > 1e-9:
        dx += (ball[0] - anchor[0]) / d_ball * (w_ball * d_ball)
        dy += (ball[1] - anchor[1]) / d_ball * (w_ball * d_ball)
    if d_rim > 1e-9:
        dx += (rim[0] - anchor[0]) / d_rim * (w_basket * d_rim)
        dy += (rim[1] - anchor[1]) / d_rim * (w_basket * d_rim)

    travel = math.hypot(dx, dy)
    if travel > reach:                      # the role class caps total movement
        dx *= reach / travel
        dy *= reach / travel

    spot = _clamp_into(anchor, (anchor[0] + dx, anchor[1] + dy), ring)
    return {"x": spot[0], "y": spot[1]}
