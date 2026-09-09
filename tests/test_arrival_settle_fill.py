"""Guards for the arrival-tail fill (defect 2).

Four contracts, each poisoned in scratch_poison_settle.py:
  1. The delay equals the player's own tween wall duration, so the wander starts as he STOPS.
     A fill that starts at the step boundary animates a man who is still travelling.
  2. Nothing below the 60ms perceptibility floor is ever stamped.
  3. Existing still-player wanders are untouched — never overwritten, never displaced.
  4. ONE density cap, shared with the still-player pass, not one cap each.

Per bugs.md item 6, this suite has a history of guards that pass for free. Every assertion here
is written against a fixture whose numbers are computed by hand in the docstrings, and the
`test_detector_fires` case exists so a change that stops stamping ANYTHING cannot make the rest
of this file vacuously green.
"""
from BackEnd.utils.animation_step_helpers import (
    ARRIVAL_SETTLE_FAMILY,
    ARRIVAL_SETTLE_HARD_FLOOR_MS,
    IDLE_STILL_DENSITY_CAP,
    stamp_arrival_settle,
)

# animationPlayback.js:1307-1310 — game-seconds to wall-clock ms.
CLOCK = 350.0


def _step(tweens, time_elapsed, flourish=None, moved=True):
    """One step. `tweens` maps player id -> tween duration in GAME seconds."""
    end_xy = {"x": 5.0, "y": 5.0} if moved else {"x": 0.0, "y": 0.0}
    step = {
        "start": {
            "coords": {p: {"x": 0.0, "y": 0.0} for p in tweens},
            "tween_durations": dict(tweens),
        },
        "end": {
            "coords": {p: dict(end_xy) for p in tweens},
            "time_elapsed": time_elapsed,
        },
    }
    if flourish:
        step["start"]["flourish"] = dict(flourish)
    return step


def _fills(step):
    return {
        p: f for p, f in (step["start"].get("flourish") or {}).items()
        if (f or {}).get("family") == ARRIVAL_SETTLE_FAMILY
    }


def test_detector_fires():
    """ANTI-VACUITY. If this stops stamping, every other test here passes for free."""
    step = _step({"a": 0.2}, 2.0)          # 700ms step, 70ms tween -> 630ms tail
    assert stamp_arrival_settle([step]) == 1
    assert set(_fills(step)) == {"a"}


def test_delay_equals_the_players_own_tween_duration():
    """Step is 2.0s = 700ms of wall clock.

    `a` tweens 1.0 game-seconds = 350ms, so he arrives at 350ms and stands for 350ms.
    `c` tweens 0.2 game-seconds =  70ms, so he arrives at  70ms and stands for 630ms.
    The delay must be the ARRIVAL time, and delay + duration must exactly span the step —
    a fill that over-runs the boundary would be cut off mid-envelope and leave a residual
    offset on a sprite the next step is about to reposition.
    """
    step = _step({"a": 1.0, "c": 0.2}, 2.0)
    stamp_arrival_settle([step])
    fills = _fills(step)
    assert set(fills) == {"a", "c"}
    for pid, tween_s in (("a", 1.0), ("c", 0.2)):
        expected_delay = max(50.0, round(tween_s * CLOCK))
        assert fills[pid]["delay_ms"] == expected_delay, pid
        assert fills[pid]["duration_ms"] == 700.0 - expected_delay, pid
        assert fills[pid]["delay_ms"] + fills[pid]["duration_ms"] == 700.0, pid


def test_sub_floor_tails_are_never_stamped():
    """`b` tweens 1.9s = 665ms of a 700ms step, leaving a 35ms tail — under the 60ms floor.

    24.7% of all tails in a game sit below this floor. Stamping them is pure cost for something
    no one can see, and it is the cheapest way to make the court read as busy for nothing.
    """
    step = _step({"a": 1.0, "b": 1.9}, 2.0)
    stamp_arrival_settle([step])
    fills = _fills(step)
    assert "b" not in fills
    assert "a" in fills, "the detector must still fire, or this test proves nothing"
    assert all(f["tail_ms"] >= ARRIVAL_SETTLE_HARD_FLOOR_MS for f in fills.values())


def test_floor_cannot_be_lowered_below_the_hard_limit():
    """The FE threshold is a tuning knob; the 60ms floor is not, and a caller cannot undercut it."""
    step = _step({"a": 1.0, "b": 1.9}, 2.0)
    stamp_arrival_settle([step], min_tail_ms=0)
    assert "b" not in _fills(step)


def test_existing_still_player_wanders_are_untouched():
    """A still-player wander already owns that sprite's idle channel. Overwriting it would
    silently replace a shipped, eye-verified behaviour with a different family's style."""
    pre = {
        "a": {"kind": "idle_wander", "family": "hco_still", "style": "survey_rock", "seed": 11},
        "z": {"kind": "reach_in"},
    }
    step = _step({"a": 0.2, "b": 0.2, "z": 0.2}, 2.0, flourish=pre)
    stamp_arrival_settle([step])
    fl = step["start"]["flourish"]
    assert fl["a"] == pre["a"], "a shipped still-player wander was overwritten"
    assert fl["z"] == pre["z"], "a non-idle flourish was overwritten"
    assert fl["b"]["family"] == ARRIVAL_SETTLE_FAMILY


def test_one_shared_density_cap_not_two():
    """A step already carrying the cap in still-player wanders gets NO fills, and a step
    carrying one gets cap-1. Two independent caps would let the court hold twice the intended
    number of men shifting about, which is the 'busy' failure the cap exists to prevent."""
    def idlers(step):
        return sum(1 for f in (step["start"].get("flourish") or {}).values()
                   if (f or {}).get("kind") == "idle_wander")

    tweens = {"p%d" % i: 0.2 for i in range(10)}

    full = {"p%d" % i: {"kind": "idle_wander", "family": "hco_still"}
            for i in range(IDLE_STILL_DENSITY_CAP)}
    step_full = _step(tweens, 2.0, flourish=full)
    assert stamp_arrival_settle([step_full]) == 0
    assert idlers(step_full) == IDLE_STILL_DENSITY_CAP

    one = {"p0": {"kind": "idle_wander", "family": "hco_still"}}
    step_one = _step(tweens, 2.0, flourish=one)
    assert stamp_arrival_settle([step_one]) == IDLE_STILL_DENSITY_CAP - 1
    assert idlers(step_one) == IDLE_STILL_DENSITY_CAP

    step_none = _step(tweens, 2.0)
    assert stamp_arrival_settle([step_none]) == IDLE_STILL_DENSITY_CAP
    assert idlers(step_none) == IDLE_STILL_DENSITY_CAP


def test_longest_tail_is_filled_first():
    """Under the cap, the men with the most dead time to fill are the ones that get filled."""
    tweens = {"p%d" % i: 0.1 * (i + 1) for i in range(10)}   # p0 has the longest tail
    step = _step(tweens, 4.0, flourish=None)
    stamp_arrival_settle([step])
    chosen = set(_fills(step))
    assert chosen == {"p%d" % i for i in range(IDLE_STILL_DENSITY_CAP)}


def test_a_player_with_no_tween_is_not_a_candidate():
    """No `tween_durations` entry means he tweens for the whole step, so his tail is zero."""
    step = _step({"a": 0.2}, 2.0)
    step["start"]["coords"]["nomove"] = {"x": 1.0, "y": 1.0}
    step["end"]["coords"]["nomove"] = {"x": 9.0, "y": 9.0}
    stamp_arrival_settle([step])
    assert "nomove" not in _fills(step)
    assert "a" in _fills(step)


def test_seed_is_derived_from_the_player_id_not_an_rng():
    """A sim_rng draw here would move the draw count and fail the 8-seed gate."""
    a = _step({"x": 0.2}, 2.0)
    b = _step({"x": 0.2}, 2.0)
    stamp_arrival_settle([a])
    stamp_arrival_settle([b])
    assert _fills(a)["x"] == _fills(b)["x"]
