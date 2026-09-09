"""The item 22 guard: authored arc spots sit EXACTLY on the classification boundary.

This is the FIRST assertion on a resolved shot-classification VALUE anywhere in the suite. Per
bugs.md item 6, every coordinate and classification change in this project has been passing the
gate for free because nothing ever asserted what a shot was worth — a deliberately wrong
coordinate produced an empty baseline delta. That is the gap this file starts to close.

WHY IT MATTERS HERE SPECIFICALLY. NINE of the authored three-point spots normalize onto the arc
boundary with a margin of exactly zero: `key` sits at normalized x=64.0 and
``_three_point_boundary_x(25.0)`` returns 64.0. The comparison is ``normalized_x <= boundary_x``,
so equality resolves as a three and the spots work. Measured on the played arm, 153 of 686
attempts (22.3%) classify off that zero margin.

A ``<=`` -> ``<`` edit is the most innocuous-looking change imaginable — a reviewer would read it
as a tidy-up — and it would reprice a fifth of every shot attempt in the league as a two. It
would surface as scoring drift across a season, not as a failing test.

SPOT NAMES ARE CASE-SPLIT ACROSS TABLES, and enumerating without accounting for it undercounts.
``THREE_POINT_SPOTS`` and ``PAINT_SPOTS`` name spots in lowercase ("lower midwing",
"basketspot"); ``HCO_STRING_SPOTS`` authors the coordinates in camelCase ("lower midWing",
"basketSpot"). A case-sensitive lookup finds five on-boundary spots and silently misses the four
mid-wing/mid-corner ones, which are ALSO at margin zero. This file resolves case-insensitively
for that reason. It is the same vocabulary-mismatch class as the spot-key converter that did not
speak its own module's vocabulary.

NOT FIXED BY MOVING THE SPOTS. Adding margin would change which shots are threes, which is a
balance change wearing a tidy-up costume, and it is deferred until after Jamie's balance pass.
The margin stays zero; this file makes the zero load-bearing and visible instead.
"""
import pytest

from BackEnd.constants import HCO_STRING_SPOTS, OFFSET_SPOTS, PAINT_SPOTS, THREE_POINT_SPOTS
from BackEnd.utils.shot_geometry import (
    _three_point_boundary_x,
    classify_shot_value,
    is_three_point_shot_from_coords,
)

# Authored arc spots whose coordinate lands ON the boundary. Derived, then pinned: the test
# recomputes the set so a spot that gains or loses margin shows up, rather than trusting this
# list. If a spot moves off the line that is a balance change and it should be argued, not
# absorbed silently by a test that only ever looked at `key`.
EXPECTED_ON_BOUNDARY = {
    "key",
    "lower corner",
    "lower midcorner",
    "lower midwing",
    "lower wing",
    "upper corner",
    "upper midcorner",
    "upper midwing",
    "upper wing",
}

_COORDS_BY_LOWER = {}
for _table in (HCO_STRING_SPOTS, OFFSET_SPOTS):
    for _name, _c in _table.items():
        if isinstance(_c, dict) and "x" in _c and "y" in _c:
            _COORDS_BY_LOWER.setdefault(str(_name).lower(), _c)


def _spot_coord(name):
    """Case-insensitive, because the name tables and the coordinate table disagree on casing."""
    return _COORDS_BY_LOWER.get(str(name).lower())


def _arc_spots_with_coords():
    return sorted(n for n in THREE_POINT_SPOTS if _spot_coord(n))


def _margin(name):
    """boundary_x - normalized_x. Zero means the spot is exactly on the line."""
    c = _spot_coord(name)
    return _three_point_boundary_x(float(c["y"])) - float(c["x"])


def _display_xy(name, *, away):
    """HCO spot constants are authored in HOME-offense orientation; away offense mirrors x."""
    c = _spot_coord(name)
    x = float(c["x"])
    return {"x": (100.0 - x) if away else x, "y": float(c["y"])}


def test_every_arc_spot_name_resolves_to_a_coordinate():
    """Coverage honesty, and the case-split trap. Every name in THREE_POINT_SPOTS must resolve,
    or this file is quietly guarding fewer spots than its docstring claims.

    Poisoned by making _spot_coord case-sensitive: the four mid-wing/mid-corner spots stop
    resolving and this fails, which is exactly the undercount that would have shipped."""
    unresolved = sorted(n for n in THREE_POINT_SPOTS if not _spot_coord(n))
    assert not unresolved, (
        "arc spot name(s) %s have no authored coordinate in HCO_STRING_SPOTS or OFFSET_SPOTS "
        "under any casing, so they are not covered by any assertion below" % unresolved
    )


def test_the_on_boundary_set_is_exactly_what_we_think_it_is():
    """If a new arc spot is authored onto the line, or an existing one is moved off it, this
    fails and names it — so the parametrised guards cannot drift out of step with the table."""
    actual = {n for n in _arc_spots_with_coords() if abs(_margin(n)) < 1e-9}
    assert actual == EXPECTED_ON_BOUNDARY, (
        "the set of arc spots sitting exactly on the classification boundary changed.\n"
        "  expected: %s\n  actual:   %s\n"
        "A spot moving off the line changes which shots are threes — that is a balance change "
        "and wants its own brief, not a test edit."
        % (sorted(EXPECTED_ON_BOUNDARY), sorted(actual))
    )


@pytest.mark.parametrize("spot", sorted(EXPECTED_ON_BOUNDARY))
@pytest.mark.parametrize("away", [False, True], ids=["home_offense", "away_offense"])
def test_on_boundary_spot_classifies_as_a_three(spot, away):
    """THE GUARD. A shot released from an authored arc spot is worth three, at both ends of the
    floor. Margin is zero, so this is exactly the assertion a ``<=`` -> ``<`` edit breaks.

    Poisoned by flipping either comparison in shot_geometry.py: all 18 parametrisations fail.
    """
    coord = _display_xy(spot, away=away)
    assert abs(_margin(spot)) < 1e-9, "%s is no longer on the boundary; see the set test" % spot

    assert is_three_point_shot_from_coords(coord, is_away_offense=away) is True, (
        "%s (%s) classified as a TWO. It sits exactly ON the arc, so the boundary comparison "
        "just stopped being inclusive — every arc spot in the game is now worth two."
        % (spot, coord)
    )

    # Both entry points, because the field-goal path goes through classify_shot_value and the
    # legacy path through is_three_point_shot_from_coords. Guarding one leaves the other open.
    payload = classify_shot_value(coord, is_away_offense=away)
    assert payload["is_three_point_shot"] is True, "%s: %r" % (spot, payload)
    assert payload["points"] == 3, "%s scored %s points" % (spot, payload["points"])
    assert payload["shot_value"] == 3


@pytest.mark.parametrize("spot", _arc_spots_with_coords())
def test_every_authored_arc_spot_is_worth_three(spot):
    """The wider population, not just the knife-edge nine. `deep key` and the deep wings carry
    real margin and should be threes for less delicate reasons — if one of THOSE flips, the arc
    table itself moved rather than the comparison."""
    for away in (False, True):
        payload = classify_shot_value(_display_xy(spot, away=away), is_away_offense=away)
        assert payload["is_three_point_shot"] is True, (
            "authored arc spot %r classified as a two (away_offense=%s): %r"
            % (spot, away, payload)
        )


def test_paint_spots_are_not_threes():
    """ANTI-VACUITY. Without this, a classifier hardcoded to return True would pass every
    assertion above. Establishes that the function actually discriminates.

    The `checked` floor is not decoration: the first draft of this test resolved names
    case-sensitively, found zero paint spots, and passed a loop that never executed. The floor
    caught it."""
    checked = 0
    for name in sorted(PAINT_SPOTS):
        c = _spot_coord(name)
        if not c:
            continue
        checked += 1
        for away in (False, True):
            coord = _display_xy(name, away=away)
            assert is_three_point_shot_from_coords(coord, is_away_offense=away) is False, (
                "paint spot %r classified as a THREE (%s) — the comparison is inverted, not "
                "merely mis-tuned" % (name, coord)
            )
            payload = classify_shot_value(coord, is_away_offense=away)
            assert payload["is_three_point_shot"] is False
            assert payload["points"] == 2
    assert checked >= 6, (
        "only %d paint spots resolved to coordinates, so this anti-vacuity check barely checked "
        "anything — PAINT_SPOTS is %s" % (checked, sorted(PAINT_SPOTS))
    )


def test_a_step_inside_the_boundary_is_a_two():
    """The other half of discrimination, at the same y as the knife-edge spots. One grid unit
    (~1ft) toward the rim from the boundary must be a two, one unit behind it a three. Together
    with the on-boundary tests this pins the comparison to the exact line rather than merely
    somewhere nearby."""
    for spot in sorted(EXPECTED_ON_BOUNDARY):
        y = float(_spot_coord(spot)["y"])
        boundary = _three_point_boundary_x(y)

        assert is_three_point_shot_from_coords(
            {"x": boundary, "y": y}, is_away_offense=False
        ) is True, "%s: on the line classified as a two" % spot
        assert is_three_point_shot_from_coords(
            {"x": boundary + 1.0, "y": y}, is_away_offense=False
        ) is False, "%s: a foot inside the arc still classified as a three" % spot
        assert is_three_point_shot_from_coords(
            {"x": boundary - 1.0, "y": y}, is_away_offense=False
        ) is True, "%s: a foot behind the arc classified as a two" % spot


def test_the_zero_margin_is_recorded_not_assumed():
    """Documents the actual numbers item 22 rests on, so the ledger entry and the code cannot
    drift apart."""
    assert (float(_spot_coord("key")["x"]), float(_spot_coord("key")["y"])) == (64.0, 25.0)
    assert _three_point_boundary_x(25.0) == 64.0
    for spot in sorted(EXPECTED_ON_BOUNDARY):
        assert _margin(spot) == 0.0, "%s margin is %r, not zero" % (spot, _margin(spot))
