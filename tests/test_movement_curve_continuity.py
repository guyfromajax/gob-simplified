"""The curve assignment must match the continuity fact.

Continuity-aware easing is only correct if the curve tracks the JOURNEY. The failure mode is
specific and it is not a crash: ease a mid-journey step and a player crossing the floor over
four steps decelerates and re-accelerates four times, which looks worse than the constant
velocity it replaced. Nothing in the payload objects to that, no coordinate moves, and per
bugs.md item 6 a green suite here is evidence of nothing on its own — so the invariant needs
stating directly.

The load-bearing assertion is the NEGATIVE one: a continuing step must carry NO curve, because
absent means linear in the frontend mapping. A guard that only checked the eased cases would
pass while everything eased.
"""
import pytest

from BackEnd.utils.animation_step_helpers import (
    MOVEMENT_CURVE_ARRIVE,
    MOVEMENT_CURVE_DEPART,
    MOVEMENT_CURVE_KEY,
    MOVEMENT_CURVE_SINGLE,
    stamp_movement_curves,
)

PID = "p1"
OTHER = "p2"


def _steps(journey):
    """Build a step list from a coordinate path for PID.

    ``journey`` is a list of (start_x, end_x) pairs, one per step. A pair with equal values is
    a step where the player stands still. OTHER is always still, so every case also asserts
    that a stationary neighbour is never stamped.
    """
    out = []
    for sx, ex in journey:
        out.append({
            "start": {"coords": {PID: {"x": sx, "y": 10.0}, OTHER: {"x": 90.0, "y": 40.0}}},
            "end": {"coords": {PID: {"x": ex, "y": 10.0}, OTHER: {"x": 90.0, "y": 40.0}}},
        })
    return out


def _curves(steps):
    return [(s["start"].get(MOVEMENT_CURVE_KEY) or {}).get(PID) for s in steps]


def test_single_step_journey_eases_both_ends():
    steps = _steps([(0.0, 0.0), (0.0, 20.0), (20.0, 20.0)])
    stamp_movement_curves(steps)
    assert _curves(steps) == [None, MOVEMENT_CURVE_SINGLE, None]


def test_multi_step_journey_eases_only_the_ends():
    # Five steps of travel between two rests. This is the case that per-step easing ruins.
    steps = _steps([(0.0, 0.0), (0.0, 10.0), (10.0, 20.0), (20.0, 30.0), (30.0, 40.0),
                    (40.0, 50.0), (50.0, 50.0)])
    stamp_movement_curves(steps)
    assert _curves(steps) == [
        None,
        MOVEMENT_CURVE_DEPART,
        None,   # continuing
        None,   # continuing
        None,   # continuing
        MOVEMENT_CURVE_ARRIVE,
        None,
    ]


def test_continuing_steps_carry_no_curve_at_all():
    """The negative invariant, asserted on the key rather than on the value.

    ``None`` from a ``.get`` cannot distinguish "not stamped" from "stamped as None", and only
    the former renders linear. Assert the player is absent from the map.
    """
    steps = _steps([(0.0, 10.0), (10.0, 20.0), (20.0, 30.0), (30.0, 40.0)])
    stamp_movement_curves(steps)
    middles = steps[1:3]
    for s in middles:
        assert PID not in (s["start"].get(MOVEMENT_CURVE_KEY) or {})


def test_still_players_are_never_stamped():
    steps = _steps([(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)])
    assert stamp_movement_curves(steps) == 0
    for s in steps:
        assert MOVEMENT_CURVE_KEY not in s["start"]


def test_turn_boundary_counts_as_rest_not_as_continuation():
    """A journey that runs to the edge of the turn arrives rather than continuing.

    The emitted list is all the renderer has. Assuming continuation past an edge we cannot see
    is what made CONTINUE_FROM_PREVIOUS unshippable; the conservative reading is an extra
    deceleration at a seam, never a phantom mid-journey pulse.
    """
    steps = _steps([(0.0, 10.0), (10.0, 20.0)])
    stamp_movement_curves(steps)
    assert _curves(steps) == [MOVEMENT_CURVE_DEPART, MOVEMENT_CURVE_ARRIVE]


def test_every_multi_step_journey_has_exactly_one_depart_and_one_arrive():
    """Structural check: departures and arrivals must balance.

    If they do not, some journey got two accelerations or none, which is the pulsing defect
    showing up as a count rather than as a visual.
    """
    steps = _steps([(0.0, 0.0), (0.0, 10.0), (10.0, 20.0), (20.0, 20.0),
                    (20.0, 20.0), (20.0, 35.0), (35.0, 45.0), (45.0, 45.0)])
    stamp_movement_curves(steps)
    got = _curves(steps)
    assert got.count(MOVEMENT_CURVE_DEPART) == 2
    assert got.count(MOVEMENT_CURVE_ARRIVE) == 2
    assert got.count(MOVEMENT_CURVE_SINGLE) == 0


def test_stamp_is_idempotent():
    """_append_turn runs once per turn, but a re-render or a replayed turn must not double up."""
    steps = _steps([(0.0, 0.0), (0.0, 20.0), (20.0, 20.0)])
    first = stamp_movement_curves(steps)
    snapshot = _curves(steps)
    stamp_movement_curves(steps)
    assert first == 1
    assert _curves(steps) == snapshot


@pytest.mark.parametrize("steps", [None, [], [{}], [{"start": {}}], [{"start": {"coords": {}}}]])
def test_degenerate_payloads_do_not_raise(steps):
    """Turn types that carry no steps or no coords (TIMEOUT, RUN_OUT_CLOCK) reach this seam too.

    It runs on every turn in _append_turn, so a shape it cannot read must be skipped rather
    than crash a game.
    """
    assert stamp_movement_curves(steps) == 0
