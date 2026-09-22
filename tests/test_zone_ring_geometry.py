"""Every zone definition in shared_defense must be a valid simple polygon.

``_point_in_zone`` treats each spot list as a polygon vertex ring IN LIST ORDER and
ray-casts it (``_point_in_polygon``). So a list that is written as a membership set
rather than a boundary walk silently becomes the wrong region: a ring that crosses
itself has an even-odd interior covering roughly half the area the spot names
describe, and a list shorter than three points is rejected outright by the ``< 3``
guard, which makes that defender unable to match anyone at all.

Both states shipped: 14 rings self-intersected and 2 were single spots. See
``reports/zone-ring-repair-2026-09-18.md``. This is the guard that would have
caught them.

When adding a spot to a zone, insert it at its position in the boundary walk.
Appending is what created the original self-intersections.
"""
from itertools import combinations

import pytest

from BackEnd.utils import shared_defense as SD

ZONE_TABLES = [
    "ZONE_23_NORMAL", "ZONE_23_LOWER_SHIFT", "ZONE_23_UPPER_SHIFT",
    "ZONE_32_NORMAL", "ZONE_32_LOWER_SHIFT", "ZONE_32_UPPER_SHIFT",
    "ZONE_131_NORMAL", "ZONE_131_LOWER_SHIFT", "ZONE_131_LOWER_CORNER_SHIFT",
    "ZONE_131_UPPER_SHIFT", "ZONE_131_UPPER_CORNER_SHIFT",
]

ALL_ZONES = [
    (table, position, spots)
    for table in ZONE_TABLES
    for position, spots in getattr(SD, table).items()
]


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_cross(p, q, r, s):
    d1, d2 = _cross(r, s, p), _cross(r, s, q)
    d3, d4 = _cross(p, q, r), _cross(p, q, s)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def self_intersections(ring):
    """Pairs of non-adjacent edges that cross. Empty for a simple polygon."""
    n = len(ring)
    if n < 4:
        return []
    return [
        (i, j)
        for i, j in combinations(range(n), 2)
        if abs(i - j) not in (1, n - 1)
        and _segments_cross(ring[i], ring[(i + 1) % n], ring[j], ring[(j + 1) % n])
    ]


@pytest.mark.parametrize("table,position,spots", ALL_ZONES,
                         ids=[f"{t}-{p}" for t, p, _ in ALL_ZONES])
def test_zone_ring_is_a_valid_simple_polygon(table, position, spots):
    ring = SD._get_zone_coords(spots, False)

    # 1. at least three DISTINCT vertices, or _point_in_polygon's `< 3` guard makes
    #    the zone match nobody, ever.
    assert len(set(ring)) >= 3, (
        f"{table}[{position!r}] has {len(set(ring))} distinct vertices; "
        f"_point_in_polygon returns False for every point, so this defender can "
        f"never match an offensive player. Spots: {spots}"
    )

    # 2. no duplicate CONSECUTIVE vertices (a zero-length edge).
    dupes = [
        (i, ring[i]) for i in range(len(ring))
        if ring[i] == ring[(i + 1) % len(ring)]
    ]
    assert not dupes, (
        f"{table}[{position!r}] repeats a vertex consecutively at {dupes}; "
        f"that is a zero-length edge. Spots: {spots}"
    )

    # 3. the ring must not cross itself, or the even-odd interior is not the
    #    region the spot names describe.
    crossings = self_intersections(ring)
    assert not crossings, (
        f"{table}[{position!r}] is self-intersecting: edge pairs {crossings[:4]} "
        f"cross. The spot list must be written as a boundary walk, not a "
        f"membership list - insert new spots in ring order, never append. "
        f"Spots: {spots}"
    )


def test_the_guard_rejects_the_shapes_that_actually_shipped():
    """Poison: the pre-repair data must fail each of the three assertions."""
    # 1. the single-spot corner-shift centre (shipped in ZONE_131_*_CORNER_SHIFT)
    with pytest.raises(AssertionError, match="distinct vertices"):
        test_zone_ring_is_a_valid_simple_polygon(
            "ZONE_131_LOWER_CORNER_SHIFT", "C", ["lower corner"])

    # 2. a consecutive duplicate
    with pytest.raises(AssertionError, match="consecutively"):
        test_zone_ring_is_a_valid_simple_polygon(
            "poison", "C", ["basketSpot", "basketSpot", "midLane", "lower lowPost"])

    # 3. the shipped ZONE_23_NORMAL["SF"] order, which crossed itself
    with pytest.raises(AssertionError, match="self-intersecting"):
        test_zone_ring_is_a_valid_simple_polygon(
            "ZONE_23_NORMAL", "SF",
            ["lower midCorner", "lower corner", "lower lowPost", "lower midPost",
             "lower apex", "lower bird", "lower midBaseline"])
