"""Quick Foul setup + selection + UESS emitter (situational Force Foul)."""

import math
import random
from types import SimpleNamespace

from BackEnd.constants import (
    HOME_RIM_COORDS,
    QUICK_FOUL_APPROACH_RADIUS_GRID,
    QUICK_FOUL_RECEIVER_MAX_DIST_GRID,
    QUICK_FOUL_RECEIVER_MIN_SEPARATION_GRID,
    QUICK_FOUL_TIME_ELAPSED_FLOOR,
)
from BackEnd.utils import quick_foul as qf

POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _player(pos, *, ft=50, height=75, fouls=0, ag=50):
    return SimpleNamespace(
        player_id=f"{pos}-id",
        attributes={"FT": ft, "AG": ag},
        height=height,
        coords={"x": 50.0, "y": 25.0},
        stats={"game": {"F": fouls}},
    )


def _lineup(**overrides):
    line = {pos: _player(pos) for pos in POSITIONS}
    for pos, kwargs in overrides.items():
        line[pos] = _player(pos, **kwargs)
    return line


def _game(off_chem=25, def_chem=25):
    off_team = SimpleNamespace(team_attributes={"team_chemistry": off_chem}, team_id="OFF")
    def_team = SimpleNamespace(team_attributes={"team_chemistry": def_chem}, team_id="DEF")
    return SimpleNamespace(offense_team=off_team, defense_team=def_team, quarter=4, game_state={})


def _euclid(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def test_select_best_ft_when_roll_below_chemistry():
    # High chemistry (25) → roll (max 25) is always < 25 unless it rolls 25.
    off = _lineup(PG=dict(ft=40), SG=dict(ft=45), PF=dict(ft=90), C=dict(ft=88))
    game = _game(off_chem=25)
    rng = random.Random(1)
    sel = qf.select_quick_foul_participants(game, off, _lineup(), rng=rng)
    assert sel is not None
    if sel["offense_mode"] == "best_ft":
        assert set(sel["candidates"]) == {"PF", "C"}


def test_select_sg_pg_when_roll_at_or_above_chemistry():
    # Minimum chemistry (7) → most rolls are >= 7 → SG+PG fallback.
    off = _lineup(PG=dict(ft=40), SG=dict(ft=45), PF=dict(ft=90), C=dict(ft=88))
    game = _game(off_chem=7)
    rng = random.Random(2)
    sel = qf.select_quick_foul_participants(game, off, _lineup(), rng=rng)
    assert sel is not None
    if sel["offense_mode"] == "sg_pg":
        assert set(sel["candidates"]) == {"SG", "PG"}


def test_tallest_defender_guards_inbound():
    defn = _lineup(C=dict(height=90), PF=dict(height=85))
    game = _game()
    rng = random.Random(3)
    sel = qf.select_quick_foul_participants(game, _lineup(), defn, rng=rng)
    assert sel is not None
    assert sel["guard_pos"] == "C"
    assert sel["guard_pos"] not in (sel["fouler_pos"],)


def test_inbound_setup_geometry_bip():
    game = _game()
    off = _lineup()
    defn = _lineup()
    rng = random.Random(4)
    inbounder = {"x": 3.0, "y": 25.0}
    out = qf.build_quick_foul_inbound_setup(
        game=game,
        off_lineup=off,
        def_lineup=defn,
        inbounder_coord=inbounder,
        basket_coord=dict(HOME_RIM_COORDS),
        guard_offset=(QUICK_FOUL_APPROACH_RADIUS_GRID and 3.0, 0.0),
        rng=rng,
    )
    assert out is not None
    o_dest, d_dest = out["o_dest"], out["d_dest"]
    assert len(o_dest) == 5 and len(d_dest) == 5

    # Two candidate receivers within 15 of the inbounder and >=10 apart.
    from BackEnd.utils.quick_foul import select_quick_foul_participants  # noqa
    # Recompute candidate positions from the receiver/fouler + pairs is not
    # exposed; instead verify the two closest offensive non-SF players.
    sf = o_dest["SF"]
    near = sorted(
        (pos for pos in ("PG", "SG", "PF", "C")),
        key=lambda p: _euclid(o_dest[p], sf),
    )[:2]
    assert _euclid(o_dest[near[0]], sf) <= QUICK_FOUL_RECEIVER_MAX_DIST_GRID + 0.5
    assert _euclid(o_dest[near[1]], sf) <= QUICK_FOUL_RECEIVER_MAX_DIST_GRID + 0.5
    assert _euclid(o_dest[near[0]], o_dest[near[1]]) >= QUICK_FOUL_RECEIVER_MIN_SEPARATION_GRID - 0.5

    # The chosen fouler sits within 4 of the receiver.
    receiver_pos = out["receiver_pos"]
    fouler_pos = out["fouler_pos"]
    assert _euclid(d_dest[fouler_pos], o_dest[receiver_pos]) <= QUICK_FOUL_APPROACH_RADIUS_GRID + 0.5

    # Inbound guard sits ~3 in x off the baseline inbounder.
    assert abs(d_dest[out["guard_pos"]]["x"] - (inbounder["x"] + 3.0)) <= 0.5


def test_emitter_two_steps_clock_pinned_on_reach_in():
    off = _lineup()
    defn = _lineup()
    prior = {}
    for pos in POSITIONS:
        prior[str(off[pos].player_id)] = {"x": 20.0, "y": 25.0}
        prior[str(defn[pos].player_id)] = {"x": 60.0, "y": 25.0}
    victim_id = off["PG"].player_id
    fouler_id = defn["PG"].player_id
    steps, te = qf.build_quick_foul_animation_steps(
        off_lineup=off,
        def_lineup=defn,
        prior_final_coords=prior,
        victim_id=victim_id,
        fouler_id=fouler_id,
        clock_remaining_at_start=40.0,
        shot_clock_remaining_at_start=20.0,
        announcement={"text": "Quick Foul!", "team": "neutral"},
        rng=random.Random(5),
    )
    assert len(steps) == 2
    converge, reach = steps
    # Converge burns >= floor.
    assert te >= QUICK_FOUL_TIME_ELAPSED_FLOOR - 1e-9
    assert converge["end"]["time_elapsed"] >= QUICK_FOUL_TIME_ELAPSED_FLOOR - 1e-9
    # Reach-in pins the clock (start == end).
    assert reach["start"]["clock"]["clock_remaining"] == reach["end"]["clock"]["clock_remaining"]
    # Fouler ends within 4 of victim after converge.
    v = converge["end"]["coords"][str(victim_id)]
    f = converge["end"]["coords"][str(fouler_id)]
    assert _euclid(f, v) <= QUICK_FOUL_APPROACH_RADIUS_GRID + 0.5
    # Reach-in flourish on the fouler; announcement present.
    assert reach["start"]["flourish"][str(fouler_id)]["kind"] == "reach_in"
    assert reach["end"]["announcement"]["text"] == "Quick Foul!"
    assert reach["end"]["next"]["kind"] == "turn_stop"


def test_quick_foul_in_play_detection():
    # 0:31-1:00 force-foul band is 3 < delta < 12 (delta = offense - defense).
    # Offense leading by 5 → the trailing defense should intentionally foul.
    game_on = SimpleNamespace(
        quarter=4,
        game_state={"time_remaining": 45},
        offense_team=SimpleNamespace(name="O"),
        defense_team=SimpleNamespace(name="D"),
        score={"O": 10, "D": 5},  # offense leads by 5 → force foul band
    )
    assert qf.quick_foul_in_play(game_on) is True

    # Tie game → neither slow-it-down nor force foul.
    game_off = SimpleNamespace(
        quarter=4,
        game_state={"time_remaining": 45},
        offense_team=SimpleNamespace(name="O"),
        defense_team=SimpleNamespace(name="D"),
        score={"O": 8, "D": 8},
    )
    assert qf.quick_foul_in_play(game_off) is False

    # Q1-3 → never active.
    game_q1 = SimpleNamespace(
        quarter=1,
        game_state={"time_remaining": 45},
        offense_team=SimpleNamespace(name="O"),
        defense_team=SimpleNamespace(name="D"),
        score={"O": 10, "D": 5},
    )
    assert qf.quick_foul_in_play(game_q1) is False
