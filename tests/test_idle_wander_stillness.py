"""Guards on the idle-wander stillness writer (animation_step_helpers.py).

The defect these lock down was AIM, not amplitude: measured on the played arm, 73.4% of
idle_wander stamps landed on a player who was MOVING for that step, where a few inches of drift
against ten-plus feet of travel is invisible. Meanwhile 45.6% of player-steps are still and
carried nothing.

Every assertion here has been poisoned — see the docstring on each test for what reinstating the
defect looks like and which assertion catches it.
"""

from BackEnd.utils.animation_step_helpers import (
    IDLE_STILL_DENSITY_CAP,
    IDLE_STILL_MIN_STEP_MS,
    _idle_crc,
    stamp_idle_wander_on_still_players,
)


def _step(coords_start, coords_end, *, ms=1000.0, flourish=None, kind=None):
    """A minimal emitted step. Duration is carried as an explicit wall-clock hold so the test
    does not depend on the clock-seconds conversion."""
    meta = {"wall_clock_hold_ms": ms}
    if kind:
        meta["kind"] = kind
    start = {
        "coords": {p: dict(c) for p, c in coords_start.items()},
        "advance_trigger": {"metadata": meta},
    }
    if flourish:
        start["flourish"] = flourish
    return {"start": start, "end": {"coords": {p: dict(c) for p, c in coords_end.items()}}}


def _wanderers(step):
    return {
        pid
        for pid, fl in ((step.get("start") or {}).get("flourish") or {}).items()
        if (fl or {}).get("kind") == "idle_wander"
    }


def _ten(still_ids, moving_ids):
    start, end = {}, {}
    for i, pid in enumerate(still_ids):
        start[pid] = {"x": 10.0 + i, "y": 20.0}
        end[pid] = {"x": 10.0 + i, "y": 20.0}
    for i, pid in enumerate(moving_ids):
        start[pid] = {"x": 40.0 + i, "y": 20.0}
        end[pid] = {"x": 47.0 + i, "y": 26.0}
    return start, end


def test_still_players_are_stamped_and_moving_players_are_not():
    """THE CORE AIM GUARD. Poisoned by dropping the `_idle_is_still` condition from the candidate
    filter so every player is stamped regardless — the pre-fix behavior. The moving-player
    assertion below fails: 4 unexpected stamps."""
    start, end = _ten(["s1", "s2", "s3"], ["m1", "m2"])
    step = _step(start, end)

    written = stamp_idle_wander_on_still_players([step], family="hco_still")

    assert written == 3
    assert _wanderers(step) == {"s1", "s2", "s3"}
    for pid in ("m1", "m2"):
        assert pid not in ((step["start"].get("flourish")) or {}), (
            "a MOVING player was given an idle wander — this is the 73.4% defect"
        )


def test_sub_perceptible_step_gets_no_idle():
    """The 60ms floor from deadAirLedger.js:87. Poisoned by setting min_step_ms=0; the assertion
    fails with 2 stamps on a 30ms step."""
    start, end = _ten(["s1", "s2"], [])
    short = _step(start, end, ms=IDLE_STILL_MIN_STEP_MS - 30.0)
    long = _step(start, end, ms=IDLE_STILL_MIN_STEP_MS + 30.0)

    assert stamp_idle_wander_on_still_players([short], family="hco_still") == 0
    assert stamp_idle_wander_on_still_players([long], family="hco_still") == 2


def test_density_cap_is_respected():
    """Poisoned by passing cap=None; the assertion fails at 10 stamps on one step."""
    ids = ["p%d" % i for i in range(10)]
    start, end = _ten(ids, [])
    step = _step(start, end)

    stamp_idle_wander_on_still_players([step], family="hco_still")

    assert len(_wanderers(step)) == IDLE_STILL_DENSITY_CAP


def test_excluded_players_and_existing_flourishes_are_left_alone():
    """The inbounding passer and the free-throw shooter have a real job. A player already
    carrying a reach_in must not have it overwritten. Poisoned by removing the `pid not in
    flourish` clause: the reach_in becomes an idle_wander and the kind assertion fails."""
    start, end = _ten(["s1", "s2", "s3"], [])
    step = _step(start, end, flourish={"s2": {"kind": "reach_in", "target": "ball"}})

    stamp_idle_wander_on_still_players([step], family="inbound", exclude=["s1"])

    assert _wanderers(step) == {"s3"}
    assert step["start"]["flourish"]["s2"]["kind"] == "reach_in"


def test_off_court_players_are_not_stamped():
    """BASELINE_INBOUND steps carry 16-20 player ids in start.coords, not ten. Without the
    on_court intersection the renderer is handed sprites for players who are not in the game.
    Poisoned by dropping the `allowed` clause: 'ghost' appears in the wanderers set."""
    start, end = _ten(["s1", "s2", "ghost"], [])
    step = _step(start, end)

    stamp_idle_wander_on_still_players([step], family="inbound", on_court=["s1", "s2"])

    assert _wanderers(step) == {"s1", "s2"}


def test_selection_is_stable_across_consecutive_steps():
    """The flicker guard. Players popping in and out of idling between steps reads as broken in
    a way that uniform stillness does not, so selection under the cap is ordered by how long the
    player has been still, then by a crc32 of his id.

    Ten players stand still for five steps; the same six must idle every step. Poisoned by
    ordering candidates on `_idle_crc(pid, index)` (a per-step hash) instead: the selected set
    changes every step and the equality assertion fails on step 2."""
    ids = ["p%d" % i for i in range(10)]
    start, end = _ten(ids, [])
    steps = [_step(start, end) for _ in range(5)]

    stamp_idle_wander_on_still_players(steps, family="hco_still")

    selected = [_wanderers(s) for s in steps]
    assert all(len(s) == IDLE_STILL_DENSITY_CAP for s in selected)
    assert all(s == selected[0] for s in selected), (
        "the idling six changed between steps — players will flicker in and out"
    )


def test_a_long_still_player_keeps_his_slot_over_a_newcomer():
    """Run-length priority, which is what makes the cap stable rather than merely deterministic.
    Six players stand still throughout; a seventh goes still later and must NOT displace any of
    them. Poisoned by removing the `-still_runs[pid]` primary key, leaving a plain crc32 sort.

    THE NEWCOMER'S ID IS LOAD-BEARING. "aa" is chosen because its crc32 is LOWER than every
    long-still player's, so under a plain crc32 sort it takes the top slot and evicts someone.
    A newcomer whose crc32 happened to lose anyway would make this test pass for the wrong
    reason and it would never catch the poison — the first draft used "late" and did exactly
    that. The anti-vacuity assertion below fails loudly if the ids are ever renamed into
    insensitivity."""
    long_ids = ["L%d" % i for i in range(IDLE_STILL_DENSITY_CAP)]
    newcomer = "aa"
    assert _idle_crc(newcomer) < max(_idle_crc(p) for p in long_ids), (
        "ANTI-VACUITY: %r must out-rank a long-still player on raw crc32, or this test cannot "
        "detect the loss of run-length priority" % newcomer
    )

    start_a, end_a = _ten(long_ids, [newcomer])
    start_b, end_b = _ten(long_ids + [newcomer], [])
    steps = [_step(start_a, end_a), _step(start_a, end_a), _step(start_b, end_b)]

    stamp_idle_wander_on_still_players(steps, family="hco_still")

    assert _wanderers(steps[2]) == set(long_ids)
    assert newcomer not in _wanderers(steps[2])


def test_seed_is_deterministic_and_draws_nothing_from_sim_rng():
    """Non-negotiable per the brief: the stamp seeds from the player id, not rng.randint.
    phase_resolution.py:4811 draws its seed from sim_rng, and a new stamp doing the same would
    consume draws and move the draw count on every downstream outcome.

    Poisoned by seeding from `random.randint`: the draw counter trips, and the two-run equality
    assertion fails as well."""
    from BackEnd.utils import sim_random

    calls = {"n": 0}
    original = sim_random.sim_rng.randint

    def counted(*a, **k):
        calls["n"] += 1
        return original(*a, **k)

    sim_random.sim_rng.randint = counted
    try:
        start, end = _ten(["s1", "s2"], [])
        first = _step(start, end)
        second = _step(start, end)
        stamp_idle_wander_on_still_players([first], family="hco_still")
        stamp_idle_wander_on_still_players([second], family="hco_still")
    finally:
        sim_random.sim_rng.randint = original

    assert calls["n"] == 0, "the idle stamp consumed a sim_rng draw"
    assert first["start"]["flourish"] == second["start"]["flourish"], (
        "two playbacks of the same step produced different idle payloads"
    )
    assert all(fl["seed"] > 0 for fl in first["start"]["flourish"].values())


def test_rolled_stash_never_survives_into_the_payload():
    """`_idle_rolled` carries the resolver's geography-aware style into the post-pass. It must be
    popped: the gate permits `flourish` and nothing else to differ, and a client has no business
    receiving emitter internals. Poisoned by changing the pop to a get — the key remains and the
    assertion fails."""
    start, end = _ten(["s1"], [])
    step = _step(start, end)
    step["_idle_rolled"] = {"s1": {"style": "jockey", "dir_x": 1.0, "dir_y": 0.0,
                                   "amplitude_grid": 0.6}}

    stamp_idle_wander_on_still_players([step], family="hco_still")

    assert "_idle_rolled" not in step
    assert step["start"]["flourish"]["s1"]["style"] == "jockey"
    assert step["start"]["flourish"]["s1"]["family"] == "hco_still"


def test_only_requested_step_kinds_are_touched():
    """Part 2 stamps `make_hold` — the deliberate zero-clock beat after a bucket — without
    touching the rest of a MAKE turn. Poisoned by dropping the `kinds` filter: the ball_flight
    step is stamped too and the assertion fails."""
    start, end = _ten(["s1", "s2"], [])
    hold = _step(start, end, kind="make_hold")
    flight = _step(start, end, kind="ball_flight")

    stamp_idle_wander_on_still_players(
        [flight, hold], family="make_hold", only_step_kinds=["make_hold"],
    )

    assert _wanderers(hold) == {"s1", "s2"}
    assert _wanderers(flight) == set()
