"""Loose-ball resolution + scramble animation.

A deflected pass (`BAT_OOB`) now stays in play half the time. See
`BackEnd/engine/loose_ball.py` and Dynamic_HCO_System.md.
"""
import math
from types import SimpleNamespace

import BackEnd.engine.loose_ball as LB
from BackEnd.engine.skeleton_step_emitter import append_hco_loose_ball_trajectory


class _RNG:
    """Scripted RNG so a test states the outcome it wants instead of hunting a seed."""

    def __init__(self, randints=None, uniforms=None, choice_index=0):
        self._randints = list(randints or [])
        self._uniforms = list(uniforms or [])
        self._choice_index = choice_index

    def randint(self, a, b):
        return self._randints.pop(0) if self._randints else a

    def uniform(self, a, b):
        return self._uniforms.pop(0) if self._uniforms else a

    def choice(self, seq):
        return seq[self._choice_index]


def _player(pid, ag=50, iq=50, ch=50):
    return SimpleNamespace(player_id=pid, attributes={"AG": ag, "IQ": iq, "CH": ch})


def _team(fight=0):
    return SimpleNamespace(team_attributes={"fight": fight})


# --- bounce spot ------------------------------------------------------------

def test_bounce_spot_always_lands_in_the_specified_band():
    contact = {"x": 50.0, "y": 25.0}
    for _ in range(2000):
        b = LB.roll_bounce_spot(contact)
        d = math.hypot(b["x"] - 50.0, b["y"] - 25.0)
        assert LB.LOOSE_BALL_BOUNCE_MIN_DIST - 1e-9 <= d <= LB.LOOSE_BALL_BOUNCE_MAX_DIST + 1e-9


def test_bounce_near_a_sideline_often_goes_out_but_mid_court_never_does():
    """This is what makes the out-of-bounds fallback organic rather than a second roll."""
    mid = sum(LB.is_in_bounds(LB.roll_bounce_spot({"x": 50.0, "y": 25.0})) for _ in range(2000))
    assert mid == 2000, "a deflection at half court can never carom off the floor"
    side = sum(LB.is_in_bounds(LB.roll_bounce_spot({"x": 50.0, "y": 2.0})) for _ in range(2000))
    assert 0.4 < side / 2000 < 0.8, side / 2000


def test_in_bounds_is_boundary_inclusive():
    # `nearest_oob_point` puts a ball exactly ON an edge; that is still on the court.
    assert LB.is_in_bounds({"x": 0.0, "y": 25.0}) is True
    assert LB.is_in_bounds({"x": 100.0, "y": 50.0}) is True
    assert LB.is_in_bounds({"x": -0.1, "y": 25.0}) is False
    assert LB.is_in_bounds({"x": 50.0, "y": 50.1}) is False


# --- scoring ----------------------------------------------------------------

def test_ability_uses_the_specified_weights():
    assert LB.loose_ball_ability(_player("p", ag=10, iq=20, ch=30)) == (
        0.3 * 10 + 0.3 * 20 + 0.4 * 30)


def test_fight_reads_through_core8_gameplay():
    """Core-8 attrs are stored +/-20 and play at +/-10 (THE RULE, team_attr_scale)."""
    assert LB._team_fight(_team(fight=20)) == 10.0
    assert LB._team_fight(_team(fight=-20)) == -10.0
    assert LB._team_fight(SimpleNamespace(team_attributes={})) == 0.0


def test_fight_is_inside_the_die_not_added_after():
    """Multiplied by the roll it is a real lever; added afterward it would be inert."""
    p, t = _player("p"), _team(fight=20)          # ability 50, fight +10
    score = LB.loose_ball_score(p, t, distance=0.0, rng=_RNG(randints=[6]))
    assert score == (50.0 + 10.0) * 6             # NOT 50*6 + 10


def test_distance_discount_is_twice_as_steep_as_rebounding():
    p, t = _player("p"), _team()
    at_scale = LB.loose_ball_score(p, t, distance=LB.LOOSE_BALL_DISTANCE_SCALE,
                                   rng=_RNG(randints=[1]))
    assert at_scale == 50.0 * 0.5                  # 1/(1+d/scale) at d == scale
    from BackEnd.constants import REBOUND_DISTANCE_SCALE
    assert LB.LOOSE_BALL_DISTANCE_SCALE == REBOUND_DISTANCE_SCALE / 2


# --- winner selection -------------------------------------------------------

def _entries(spec):
    return [(pos, _player(f"id-{pos}"), {"x": x, "y": y}) for pos, x, y in spec]


def test_radius_filter_excludes_distant_players():
    """A player outside the radius cannot win no matter how well he rolls."""
    bounce = {"x": 50.0, "y": 25.0}
    off = _entries([("PG", 51.0, 25.0)])                 # 1 away
    dfn = _entries([("SG", 50.0 + LB.LOOSE_BALL_CANDIDATE_RADIUS + 5, 25.0)])
    for _ in range(200):
        w = LB.select_loose_ball_recoverer(
            bounce_spot=bounce, off_entries=off, def_entries=dfn,
            off_team=_team(), def_team=_team())
        assert w["position"] == "PG"


def test_radius_expands_when_nobody_is_close_enough():
    """A ball on the floor is always recovered by SOMEONE — an empty pool is never valid."""
    bounce = {"x": 50.0, "y": 25.0}
    far = _entries([("PG", 50.0, 25.0 + LB.LOOSE_BALL_CANDIDATE_RADIUS + 8)])
    w = LB.select_loose_ball_recoverer(
        bounce_spot=bounce, off_entries=far, def_entries=[],
        off_team=_team(), def_team=_team())
    assert w is not None and w["position"] == "PG"


def test_no_players_at_all_returns_none():
    assert LB.select_loose_ball_recoverer(
        bounce_spot={"x": 50.0, "y": 25.0}, off_entries=[], def_entries=[],
        off_team=_team(), def_team=_team()) is None


def test_offense_and_defense_are_scored_on_equal_footing():
    """Unlike rebounds, there is no box-out discount — a scramble has no possession bias."""
    bounce = {"x": 50.0, "y": 25.0}
    off_wins = 0
    trials = 4000
    for _ in range(trials):
        w = LB.select_loose_ball_recoverer(
            bounce_spot=bounce,
            off_entries=_entries([("PG", 53.0, 25.0)]),
            def_entries=_entries([("PG", 47.0, 25.0)]),   # identical distance + attrs
            off_team=_team(), def_team=_team())
        off_wins += w["is_offense"]
    assert 0.45 < off_wins / trials < 0.55, off_wins / trials


def test_ties_break_at_random_not_by_pool_order():
    """Specified behaviour: no rebound-style modifier/MO/chemistry ladder."""
    bounce = {"x": 50.0, "y": 25.0}
    w = LB.select_loose_ball_recoverer(
        bounce_spot=bounce,
        off_entries=_entries([("PG", 52.0, 25.0)]),
        def_entries=_entries([("PG", 48.0, 25.0)]),
        off_team=_team(), def_team=_team(),
        rng=_RNG(randints=[3, 3], choice_index=1))       # equal scores → choice()
    assert w["is_offense"] is False                      # index 1 == the defender


# --- timing -----------------------------------------------------------------

def test_scramble_ends_when_the_ball_lands_and_the_winner_arrives():
    contact, bounce = {"x": 50.0, "y": 25.0}, {"x": 62.0, "y": 25.0}
    bounce_t, recover_t = LB.scramble_timing(
        contact=contact, bounce_spot=bounce,
        winner_coords={"x": 80.0, "y": 25.0}, winner_rate_grid_per_game_sec=18.0)
    assert bounce_t == 12.0 / LB.LOOSE_BALL_BOUNCE_GRID_PER_GAME_SEC
    assert bounce_t + recover_t == 18.0 / 18.0            # total == winner's travel


def test_winner_already_on_the_spot_needs_no_recovery_leg():
    bounce_t, recover_t = LB.scramble_timing(
        contact={"x": 50.0, "y": 25.0}, bounce_spot={"x": 58.0, "y": 25.0},
        winner_coords={"x": 58.0, "y": 25.0}, winner_rate_grid_per_game_sec=18.0)
    assert recover_t == 0.0 and bounce_t > 0.0


# --- the appended animation -------------------------------------------------

def _prior_step(ids, ball_owner):
    coords = {pid: {"x": 40.0 + 4 * i, "y": 25.0} for i, pid in enumerate(ids)}
    return {
        "start": {"coords": dict(coords), "destination": {}, "action": {}, "archetype": {}},
        "end": {
            "coords": coords,
            "ball": {"owner_player_id": ball_owner},
            "clock": {"clock_remaining": 400.0, "shot_clock_remaining": 20.0},
            "next": {"kind": "next_step", "index": 999},
        },
    }


def _lineups():
    off = {p: _player(f"off-{p}") for p in ("PG", "SG", "SF", "PF", "C")}
    dfn = {p: _player(f"def-{p}") for p in ("PG", "SG", "SF", "PF", "C")}
    return off, dfn


def _run_emitter(recoverer_id="def-C", bounce=None):
    off, dfn = _lineups()
    ids = [getattr(p, "player_id") for p in list(off.values()) + list(dfn.values())]
    steps = [_prior_step(ids, "off-PG")]
    result = {"loose_ball": {
        "contact": {"x": 52.0, "y": 25.0},
        "bounce_spot": bounce or {"x": 60.0, "y": 30.0},
        "deflector_id": "def-PG",
        "recoverer_id": recoverer_id,
        "passer_id": "off-PG",
    }}
    ok = append_hco_loose_ball_trajectory(steps, result, off, dfn)
    return ok, steps


def test_emitter_appends_the_three_scramble_beats():
    ok, steps = _run_emitter()
    assert ok is True
    reasons = [s["start"]["advance_trigger"]["metadata"]["reason"] for s in steps[1:]]
    assert reasons == ["hco_loose_ball_contact", "hco_loose_ball_bounce",
                       "hco_loose_ball_recover"]


def test_emitter_does_not_borrow_the_bat_oob_reason_strings():
    """Those suppress the frontend's imperative OOB ball-send. This ball is in play."""
    _ok, steps = _run_emitter()
    for s in steps[1:]:
        assert s["start"]["advance_trigger"]["metadata"]["reason"] not in (
            "hct_bat_oob_contact", "hct_bat_oob_drift")


def test_every_player_breaks_for_the_ball_on_the_bounce_beat():
    """The scramble must not be the deflector moving while nine players freeze."""
    _ok, steps = _run_emitter()
    bounce_step = steps[2]
    movers = [pid for pid, dest in bounce_step["start"]["destination"].items()
              if dest and dest != bounce_step["start"]["coords"][pid]]
    assert len(movers) == 10, movers


def test_ball_ends_with_the_recoverer_at_the_bounce_spot():
    _ok, steps = _run_emitter()
    end = steps[-1]["end"]
    assert end["ball"]["owner_player_id"] == "def-C"
    assert end["ball"]["coords"] == {"x": 60.0, "y": 30.0}
    assert end["coords"]["def-C"] == {"x": 60.0, "y": 30.0}


def test_clock_decrements_monotonically_across_the_scramble():
    _ok, steps = _run_emitter()
    clocks = [s["end"]["clock"]["clock_remaining"] for s in steps]
    assert clocks == sorted(clocks, reverse=True)
    assert all(c >= 0 for c in clocks)
    # Each step's own T is what it burns — the turn's time_elapsed is derived from these.
    for s in steps[1:]:
        burn = s["start"]["clock"]["clock_remaining"] - s["end"]["clock"]["clock_remaining"]
        assert abs(burn - s["end"]["time_elapsed"]) < 1e-6


def test_step_chain_indices_are_contiguous():
    _ok, steps = _run_emitter()
    for i, s in enumerate(steps[:-1]):
        assert s["end"]["next"] == {"kind": "next_step", "index": i + 1}, i


def test_last_scramble_step_inherits_the_turn_terminal():
    """REGRESSION: the terminal must be captured BEFORE `last_end["next"]` is
    repointed at Step A. Reading it back afterwards made the final step loop to the
    contact beat and discarded the real `turn_stop`."""
    off, dfn = _lineups()
    for recoverer, beats in (("def-C", 3), ("def-SG", 2)):   # 3-beat and 2-beat paths
        terminal = {"kind": "turn_stop", "event": "dead_ball_turnover"}
        ids = [p.player_id for p in list(off.values()) + list(dfn.values())]
        steps = [_prior_step(ids, "off-PG")]
        steps[0]["end"]["next"] = dict(terminal)
        assert append_hco_loose_ball_trajectory(steps, {"loose_ball": {
            "contact": {"x": 52.0, "y": 25.0}, "bounce_spot": {"x": 60.0, "y": 30.0},
            "deflector_id": "def-PG", "recoverer_id": recoverer,
            "passer_id": "off-PG"}}, off, dfn) is True
        assert len(steps) == 1 + beats, (recoverer, len(steps))
        assert steps[-1]["end"]["next"] == terminal, recoverer
        # ...and nothing points backwards.
        for i, s in enumerate(steps[:-1]):
            assert s["end"]["next"]["index"] == i + 1, (recoverer, i)


def test_emitter_is_a_noop_without_a_loose_ball_block():
    off, dfn = _lineups()
    steps = [_prior_step(["off-PG"], "off-PG")]
    assert append_hco_loose_ball_trajectory(steps, {}, off, dfn) is False
    assert append_hco_loose_ball_trajectory(steps, {"bat_oob": True}, off, dfn) is False
    assert len(steps) == 1


def test_emitter_never_double_appends():
    ok, steps = _run_emitter()
    assert ok is True
    n = len(steps)
    off, dfn = _lineups()
    assert append_hco_loose_ball_trajectory(steps, {"loose_ball": {
        "contact": {"x": 52.0, "y": 25.0}, "bounce_spot": {"x": 60.0, "y": 30.0},
        "deflector_id": "def-PG", "recoverer_id": "def-C", "passer_id": "off-PG",
    }}, off, dfn) is False
    assert len(steps) == n


def test_recoverer_who_beats_the_ball_there_skips_the_recovery_beat():
    """`def-SG` starts nearer the bounce spot than the ball's own carom time, so the
    scramble is over the instant it lands — two beats, ball already in his hands."""
    ok, steps = _run_emitter(recoverer_id="def-SG")
    assert ok is True
    reasons = [s["start"]["advance_trigger"]["metadata"]["reason"] for s in steps[1:]]
    assert reasons == ["hco_loose_ball_contact", "hco_loose_ball_bounce"]
    end = steps[-1]["end"]
    assert end["ball"] == {"coords": {"x": 60.0, "y": 30.0},
                           "owner_player_id": "def-SG"}
    assert end["coords"]["def-SG"] == {"x": 60.0, "y": 30.0}
    assert end["next"] == {"kind": "next_step", "index": 999}


# --- the 50/50 split and the resolver ---------------------------------------

def test_half_of_deflections_stay_in_play():
    kept = sum(LB.deflection_stays_in_play() for _ in range(20000))
    assert 0.47 < kept / 20000 < 0.53, kept / 20000
    # One draw, always taken, so the gameplay stream advances the same either way.
    assert LB.deflection_stays_in_play(_RNG(randints=[LB.LOOSE_BALL_FROM_DEFLECTION_PCT])) is True
    assert LB.deflection_stays_in_play(_RNG(randints=[LB.LOOSE_BALL_FROM_DEFLECTION_PCT + 1])) is False


def _resolver_args(stamped=True):
    import BackEnd.engine.phase_resolution as PR
    step = {
        "pos_actions": {p: {"location": "key", "action": "drift"}
                        for p in ("PG", "SG", "SF", "PF", "C")},
    }
    step["pos_actions"]["PG"]["action"] = "pass"
    step["pos_actions"]["SG"]["action"] = "receive"
    if stamped:
        step["_step_state"] = {"defense": {
            p: {"x": 50.0 + i, "y": 25.0} for i, p in enumerate(("PG", "SG", "SF", "PF", "C"))}}
    off = {p: _player(f"off-{p}") for p in ("PG", "SG", "SF", "PF", "C")}
    dfn = {p: _player(f"def-{p}") for p in ("PG", "SG", "SF", "PF", "C")}
    contest = {"outcome": "BAT_OOB", "deflector": "SG",
               "contact_point": {"x": 50.0, "y": 25.0}}
    game = SimpleNamespace(defense_team=_team(), offense_team=_team())
    return PR, dict(
        step=step, contest=contest, passer="PG", off_lineup=off, def_lineup=dfn,
        off_to_def={p: p for p in off}, is_away_offense=False, def_aggr="normal",
        zone=False, game_state={"defense_playcall": "man"}, off_team=_team(),
        game=game)


def test_resolver_falls_back_to_oob_without_a_stamped_defender_grid():
    """Mixing a HOME-frame zone reconstruction with display-frame offense coords would
    put the bounce spot on the wrong end of the floor. Degrade instead."""
    PR, kw = _resolver_args(stamped=False)
    assert PR._hco_resolve_loose_ball(rng=_RNG(randints=[1]), **kw) is None


def test_resolver_returns_a_scramble_payload_when_the_ball_stays_in_play():
    PR, kw = _resolver_args()
    out = PR._hco_resolve_loose_ball(rng=None, **kw)
    tries = 0
    while out is None and tries < 200:          # the 50/50 + the OOB check
        out = PR._hco_resolve_loose_ball(rng=None, **kw)
        tries += 1
    assert out is not None
    assert set(out) >= {"contact", "bounce_spot", "deflector_pos", "recoverer_pos",
                        "recoverer_id", "recovered_by_offense", "passer_pos"}
    assert LB.is_in_bounds(out["bounce_spot"])
    assert out["passer_pos"] == "PG" and out["deflector_pos"] == "SG"


def test_resolver_declines_when_the_coin_says_out_of_bounds():
    PR, kw = _resolver_args()
    over = LB.LOOSE_BALL_FROM_DEFLECTION_PCT + 1
    assert PR._hco_resolve_loose_ball(rng=_RNG(randints=[over]), **kw) is None


# --- the finalizers ---------------------------------------------------------

def _finalizer_env(monkeypatch, by_offense, shot_clock=20.0):
    import BackEnd.engine.phase_resolution as PR
    monkeypatch.setattr(PR, "apply_stopper_system_to_skeleton",
                        lambda src, kind, gs: {"steps": [{"pos_actions": {}}]})
    monkeypatch.setattr(PR, "calc_skeleton_step_timing_contract",
                        lambda *a, **k: {"time_elapsed": 3, "step_clock_seconds": [3.0],
                                         "resolution_step_index": 0, "executed_step_count": 1})
    monkeypatch.setattr(PR, "_hco_last_pass_step_index", lambda steps: None)
    off = {p: _player(f"off-{p}") for p in ("PG", "SG", "SF", "PF", "C")}
    dfn = {p: _player(f"def-{p}") for p in ("PG", "SG", "SF", "PF", "C")}
    info = {"skeleton": {"steps": []}, "passer_pos": "PG", "loose_ball": {
        "contact": {"x": 50.0, "y": 25.0}, "bounce_spot": {"x": 58.0, "y": 30.0},
        "deflector_pos": "SG", "recoverer_pos": "SF" if by_offense else "C",
        "recovered_by_offense": by_offense, "passer_pos": "PG"}}
    game_state = {"shot_clock_remaining": shot_clock}
    game = SimpleNamespace(
        offense_team=SimpleNamespace(team_id="HOME", lineup=off),
        defense_team=SimpleNamespace(team_id="AWAY", lineup=dfn),
        game_state=game_state)
    return PR, info, game, {"ball_handler": off["PG"]}, off, dfn, game_state


def test_offense_recovery_continues_the_possession_without_a_shot_clock_reset(monkeypatch):
    PR, info, game, roles, off, dfn, gs = _finalizer_env(monkeypatch, by_offense=True)
    r = PR._finalize_hco_loose_ball(info, game, roles, off, dfn, gs)
    assert r["possession_flips"] is False
    assert r["turnover_type"] == "" and r["victim_id"] is None
    assert (r["next_turn"], r["next_play_type"]) == ("HCO", "HCO")
    assert r["kickout_deferred_to_hco_entry"] is True     # reuses the OREB handoff
    assert r["loose_ball_recovered_by"] == "OFFENSE"
    assert r["is_interception"] is False
    assert "forced_shot_next" not in r
    # No reset: `_should_reset_shot_clock` returns False for a non-flipping,
    # non-rebound, non-foul result — so this needs no clock-policy change.
    assert r["result_type"] == "DEAD BALL" and not r.get("rebound_type")


def test_offense_recovery_under_the_threshold_arms_the_forced_shot(monkeypatch):
    PR, info, game, roles, off, dfn, gs = _finalizer_env(
        monkeypatch, by_offense=True, shot_clock=LB.LOOSE_BALL_FORCED_SHOT_CLOCK - 1)
    r = PR._finalize_hco_loose_ball(info, game, roles, off, dfn, gs)
    assert r["forced_shot_next"] is True
    assert r["forced_shot_reason"] == "LOOSE_BALL_LOW_SHOT_CLOCK"
    assert gs["_loose_ball_forced_shot_pending"] is True


def test_offense_recovery_at_the_threshold_does_not_arm_it(monkeypatch):
    PR, info, game, roles, off, dfn, gs = _finalizer_env(
        monkeypatch, by_offense=True, shot_clock=LB.LOOSE_BALL_FORCED_SHOT_CLOCK)
    r = PR._finalize_hco_loose_ball(info, game, roles, off, dfn, gs)
    assert "forced_shot_next" not in r
    assert "_loose_ball_forced_shot_pending" not in gs


def test_defense_recovery_credits_the_passer_with_the_turnover(monkeypatch):
    PR, info, game, roles, off, dfn, gs = _finalizer_env(monkeypatch, by_offense=False)
    seen = {}

    def fake_turnover(to_roles, g, turnover_type=None, from_resolution_system=False):
        seen["victim"] = to_roles["ball_handler"].player_id
        seen["stealer"] = to_roles["defender"].player_id
        seen["type"] = turnover_type
        return {"result_type": "TURNOVER", "possession_flips": True}

    monkeypatch.setattr(PR, "resolve_turnover_logic", fake_turnover)
    r = PR._finalize_hco_loose_ball(info, game, roles, off, dfn, gs)
    assert seen == {"victim": "off-PG", "stealer": "def-C", "type": "STEAL"}
    assert r["loose_ball_recovered_by"] == "DEFENSE"
    assert r["possession_flips"] is True          # → Rule 1 resets the shot clock
    # NOT an interception: that headline/SFX would misread a ball won on the floor.
    assert r["is_interception"] is False
    # The next possession starts where the ball was PICKED UP, not at the deflection.
    assert gs["last_stealer_coords"] == {"x": 58.0, "y": 30.0}


def test_emitted_steps_conform_to_the_animation_step_vocabularies():
    """Every action / archetype / trigger must be a value the renderer knows."""
    import typing
    from BackEnd.utils.animation_step_schema import (
        PlayerAction, PlayerArchetype, TriggerCondition,
    )
    actions = set(typing.get_args(PlayerAction))
    archetypes = set(typing.get_args(PlayerArchetype))
    triggers = set(typing.get_args(TriggerCondition))

    for recoverer in ("def-C", "def-SG", "off-SF"):
        _ok, steps = _run_emitter(recoverer_id=recoverer)
        for s in steps[1:]:
            start = s["start"]
            assert set(start["action"].values()) <= actions, start["action"]
            assert set(start["archetype"].values()) <= archetypes, start["archetype"]
            assert start["advance_trigger"]["condition"] in triggers
            assert start["advance_trigger"]["T_game_seconds"] > 0
            # Every player carries coords, a destination, an action and an archetype.
            ids = set(start["coords"])
            for key in ("destination", "action", "archetype"):
                assert set(start[key]) == ids, (key, recoverer)
            assert set(s["end"]["coords"]) == ids


# --- announcer call ---------------------------------------------------------

def test_announcer_call_is_drawn_from_the_presentation_stream():
    """Presentation must never perturb gameplay: adding or removing a clip cannot
    shift a basketball outcome. See `BackEnd/utils/sim_random`."""
    from BackEnd.utils.sim_random import sim_rng, announcement_rng
    before = sim_rng.getstate()
    for _ in range(50):
        LB.pick_loose_ball_sfx()
    assert sim_rng.getstate() == before, "the announcer draw advanced the gameplay stream"
    # ...and it does advance the presentation stream.
    ann_before = announcement_rng.getstate()
    LB.pick_loose_ball_sfx()
    assert announcement_rng.getstate() != ann_before


def test_both_announcers_are_picked_about_evenly():
    import collections
    c = collections.Counter(LB.pick_loose_ball_sfx() for _ in range(4000))
    assert set(c) == set(LB.LOOSE_BALL_SFX_FILES)
    for f in LB.LOOSE_BALL_SFX_FILES:
        assert 0.45 < c[f] / 4000 < 0.55, (f, c[f] / 4000)


def test_call_fires_at_the_moment_of_the_deflection():
    """Step A ends when the ball reaches the deflector, so Step B's step-start IS
    the instant the ball comes loose."""
    _ok, steps = _run_emitter()
    bounce_step = steps[2]
    assert bounce_step["start"]["advance_trigger"]["metadata"]["reason"] == "hco_loose_ball_bounce"
    sfx = bounce_step["start"]["sfx_on_step_start"]
    assert sfx["file"] in LB.LOOSE_BALL_SFX_FILES
    assert sfx["event"] == "loose_ball"
    assert 0.0 < sfx["volume"] <= 1.0


def test_call_does_not_displace_the_contact_thud():
    """`block1.wav` on Step A is the physical contact; the two layer, not replace."""
    _ok, steps = _run_emitter()
    assert steps[1]["start"]["sfx_on_ball_arrival"]["file"] == "block1.wav"
    assert "sfx_on_step_start" not in steps[1]["start"]
    # And exactly one announcer call per loose ball — not one per scramble beat.
    calls = [s for s in steps if (s["start"].get("sfx_on_step_start") or {}).get("event") == "loose_ball"]
    assert len(calls) == 1


def test_clips_are_registered_in_the_frontend_preload_manifest():
    """`playGameSfx` needs a preloaded pool — an unlisted file warns and plays nothing,
    so a clip added on the backend alone is silently inaudible."""
    import pathlib, re
    js = pathlib.Path("FrontEnd/static/js/phaser/utils/gameSfx.js").read_text()
    block = js.split("GAMEPLAY_SFX_FILES = Object.freeze([", 1)[1].split("]);", 1)[0]
    listed = set(re.findall(r'"([^"]+)"', block))
    sounds = pathlib.Path("FrontEnd/static/sounds")
    for f in LB.LOOSE_BALL_SFX_FILES:
        assert f in listed, f"{f} is not in GAMEPLAY_SFX_FILES — it would never play"
        assert (sounds / f).exists(), f"{f} is not in FrontEnd/static/sounds"
