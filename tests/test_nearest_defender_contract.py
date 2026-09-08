"""The contract of ``select_defender_closest_to_victim``: the charged defender is the NEAREST one.

WHY THIS TEST EXISTS AND WHY IT IS SHAPED LIKE THIS. The bug it guards (bugs.md item 24) was
not a wrong formula. The Euclidean arithmetic was correct throughout. The defect was that the
function fed itself a coordinate it had invented — ``HCO_STRING_SPOTS.get(pos, {"x": 50,
"y": 25})``, where ``pos`` is a POSITION CODE and the table is keyed by SPOT NAMES, so the
lookup could never hit. Every defender collapsed to centre court, every distance came out
equal, ``dist_sq < best_dist_sq`` was False after the first candidate, and the winner was
whichever key ``def_lineup`` happened to iterate first. Measured: 4 of 12 calls across 8 played
games, charging the wrong defender in 3 of them.

So asserting "the distance maths is right" would have passed the whole time. These assertions
are on the RESOLVED IDENTITY of the charged defender against an independently computed nearest,
because that is the only statement the defect could ever have falsified.

Draw counts cannot see this defect — both branches consume the same ``random.randint`` draws —
so this contract is the only meaningful guard on the function.
"""

import math

import pytest

from BackEnd.engine.phase_resolution import (
    _usable_grid_coord,
    select_defender_closest_to_victim,
)


class _Player:
    def __init__(self, player_id, coords):
        self.player_id = player_id
        self.coords = coords

    def __repr__(self):
        return "<%s at %s>" % (self.player_id, self.coords)


def _lineup(**by_pos):
    return {pos: _Player(pos, coords) for pos, coords in by_pos.items()}


# Five defenders at genuinely different places. Deliberately ordered so that the nearest
# defender is NOT the first one iterated for any of the victim positions below — otherwise
# iteration order and distance would agree and the test could not tell them apart.
SPREAD = dict(
    PG={"x": 88.0, "y": 25.0},
    SG={"x": 20.0, "y": 8.0},
    SF={"x": 50.0, "y": 44.0},
    PF={"x": 72.0, "y": 6.0},
    C={"x": 33.0, "y": 41.0},
)


def _nearest_pos(victim, spread):
    vx, vy = victim["x"], victim["y"]
    return min(spread, key=lambda p: math.hypot(spread[p]["x"] - vx, spread[p]["y"] - vy))


@pytest.mark.parametrize("victim", [
    {"x": 21.0, "y": 9.0},    # right on top of SG, who iterates second
    {"x": 70.0, "y": 5.0},    # PF, fourth
    {"x": 34.0, "y": 40.0},   # C, last
    {"x": 86.0, "y": 24.0},   # PG, first — the one case where order and distance agree
    {"x": 50.0, "y": 46.0},   # SF, third
    {"x": 50.0, "y": 25.0},   # centre court, the old fabricated default: still a real answer
])
def test_charged_defender_is_the_nearest_from_player_coords(victim):
    """With no coords passed, the function must read ``player.coords`` and pick the nearest.

    This is the exact call shape of the live caller (turn_manager.py:2639) — it passes None for
    ``defender_coords_by_pos`` — and it is the shape that was broken.
    """
    lineup = _lineup(**SPREAD)
    got = select_defender_closest_to_victim(victim, lineup, None)
    assert got is not None, "a lineup with five placed defenders must yield a defender"
    assert got.player_id == _nearest_pos(victim, SPREAD), (
        "charged %s but %s is nearer to %s" % (got.player_id, _nearest_pos(victim, SPREAD), victim)
    )


def test_explicit_coords_still_win_over_player_coords():
    """``defender_coords_by_pos`` remains authoritative where it supplies a position.

    turn_manager.py:619 passes real per-position destinations and that path was never broken;
    this pins it so the fix cannot quietly start ignoring the argument.
    """
    lineup = _lineup(**SPREAD)
    # Explicitly place PF on top of the victim, contradicting his player.coords.
    override = {"PF": {"x": 5.0, "y": 5.0}}
    got = select_defender_closest_to_victim({"x": 5.0, "y": 5.0}, lineup, override)
    assert got.player_id == "PF"


def test_defender_without_coords_is_skipped_not_placed_at_centre_court():
    """A coordless defender must not be given a stand-in position.

    The victim sits at centre court. If a coordless defender were defaulted to {50, 25} — the
    old behaviour — he would be exactly on the victim and would win every time. He must instead
    be skipped, and the nearest PLACED defender charged.
    """
    lineup = _lineup(
        PG={"x": 88.0, "y": 25.0},
        SG=None,
        SF={"x": 52.0, "y": 27.0},
    )
    lineup["SG"] = _Player("SG", None)
    got = select_defender_closest_to_victim({"x": 50.0, "y": 25.0}, lineup, None)
    assert got is not None
    assert got.player_id == "SF", (
        "charged %s; a coordless defender was placed at centre court instead of skipped"
        % got.player_id
    )


def test_partial_coords_are_not_usable():
    """``{"x": 40}`` with no y is not a coordinate. Half a position is not a position."""
    assert _usable_grid_coord({"x": 40.0}) is None
    assert _usable_grid_coord({"y": 40.0}) is None
    assert _usable_grid_coord({"x": None, "y": 3.0}) is None
    assert _usable_grid_coord({"x": "not a number", "y": 3.0}) is None
    assert _usable_grid_coord({"x": 40, "y": 3}) == (40.0, 3.0)


def test_no_placed_defender_returns_none_rather_than_an_arbitrary_player():
    """If nobody can be placed, say so. Do not hand back a player as though he were measured.

    A None return means "no defender can be placed". The caller may decide what to do with
    that; what it must not silently become is "the first man in the dict".
    """
    lineup = {"PG": _Player("PG", None), "SG": _Player("SG", {}), "SF": _Player("SF", None)}
    assert select_defender_closest_to_victim({"x": 50.0, "y": 25.0}, lineup, None) is None


def test_unusable_victim_coord_returns_none():
    lineup = _lineup(**SPREAD)
    assert select_defender_closest_to_victim(None, lineup, None) is None
    assert select_defender_closest_to_victim({}, lineup, None) is None
    assert select_defender_closest_to_victim({"x": 5.0}, lineup, None) is None


def test_empty_lineup_returns_none():
    assert select_defender_closest_to_victim({"x": 50.0, "y": 25.0}, {}, None) is None


def test_iteration_order_does_not_decide_the_winner():
    """THE ANTI-VACUITY ASSERTION, and the one the old code could not have passed.

    Same five defenders, same victim, but the lineup dict built in several different insertion
    orders. A distance-based selector returns the same man every time; an order-based one
    returns whoever happens to be first. Under the old fabricated-coordinate behaviour all five
    distances were equal, so this test would have returned five different defenders.
    """
    victim = {"x": 21.0, "y": 9.0}
    expected = _nearest_pos(victim, SPREAD)
    orders = [
        ["PG", "SG", "SF", "PF", "C"],
        ["C", "PF", "SF", "SG", "PG"],
        ["SF", "C", "PG", "SG", "PF"],
        ["PF", "PG", "C", "SF", "SG"],
        ["SG", "SF", "PF", "C", "PG"],
    ]
    charged = set()
    for order in orders:
        lineup = {pos: _Player(pos, SPREAD[pos]) for pos in order}
        got = select_defender_closest_to_victim(victim, lineup, None)
        charged.add(got.player_id)
    assert charged == {expected}, (
        "iteration order changed the charged defender: got %s across %d orderings"
        % (sorted(charged), len(orders))
    )
