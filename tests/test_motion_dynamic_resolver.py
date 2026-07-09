"""Phase 3 tests — Dynamic HCO Motion resolver integration (walk + shot handoff)."""
import random
import BackEnd.engine.phase_resolution as PR
from BackEnd.engine.phase_resolution import (
    _dynamic_hco_motion_enabled,
    _resolve_motion_offense_shot_dynamic,
    _execute_motion_decision,
)

_ATTR_KEYS = ["SC", "ST", "AG", "SH", "ID", "OD", "IQ", "CH"]


class _FakePlayer:
    def __init__(self, pid, **overrides):
        self.player_id = pid
        self.attributes = {k: 50 for k in _ATTR_KEYS}
        self.attributes.update(overrides)


class _FakeTeam:
    def __init__(self, team_id, is_user_team=False):
        self.team_id = team_id
        self.is_user_team = is_user_team
        self.team_attributes = {
            "discipline": 0, "fight": 0, "offensive_efficiency": 0,
            "defensive_efficiency": 0, "team_chemistry": 7,
        }
        self.strategy_calls = {"aggression_call": "normal", "tempo_call": "normal"}
        # 4/4 → turn-level gate always passes (roll 0-4 <= 4) → both teams engaged (Condition 1),
        # preserving the pre-gate resolver behavior these tests assert.
        self.strategy_settings = {"alterations": 4, "aggression": 4}


class _FakeGame:
    def __init__(self, defense_playcall="Man", shot_clock=30):
        self.home_team = _FakeTeam("HOME")
        self.away_team = _FakeTeam("AWAY")
        self.offense_team = self.home_team
        self.defense_team = self.away_team
        self.game_state = {"defense_playcall": defense_playcall, "shot_clock_remaining": shot_clock}


def _step(locations, ts=0):
    return {"timestamp": ts,
            "pos_actions": {p: {"location": loc, "action": "handle_ball"} for p, loc in locations.items()},
            "events": []}


def _skeleton(*step_locs):
    return {"steps": [_step(loc, ts=i * 1000) for i, loc in enumerate(step_locs)]}


def _lineup(**by_pos):
    return by_pos


# ---------------------------------------------------------------- gate

def test_gate_on_by_default(monkeypatch):
    # Ships ON by default (kill switch: GOB_DYNAMIC_HCO_MOTION=0).
    monkeypatch.delenv("GOB_DYNAMIC_HCO_MOTION", raising=False)
    assert _dynamic_hco_motion_enabled() is True


def test_gate_on_when_env_truthy(monkeypatch):
    for v in ("1", "true", "on", "YES"):
        monkeypatch.setenv("GOB_DYNAMIC_HCO_MOTION", v)
        assert _dynamic_hco_motion_enabled() is True


def test_turn_gate_both_off_still_resolves(monkeypatch):
    # alterations 0 + aggression 0 → neither team engaged (no subtle/disruption movement), but
    # the shoot decision is UNIVERSAL: the resolver still walks (should_shoot per step + an
    # end-of-walk forced shot) and returns a result rather than deferring to legacy.
    game = _FakeGame()
    game.offense_team.strategy_settings = {"alterations": 0}
    game.defense_team.strategy_settings = {"aggression": 0}
    monkeypatch.setattr(random, "randint", lambda a, b: b)  # max rolls → 4 <= 0 is False → both off
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot", lambda *a, **k: None)
    off = _lineup(PG=_FakePlayer("pg"))
    skel = _skeleton({"PG": "key"}, {"PG": "upper wing"})
    res = _resolve_motion_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    assert res is not None and "skeleton" in res  # walks + end-of-walk forced shot, no defer


def test_should_shoot_fires_per_step(monkeypatch):
    # The universal per-step shoot decision terminates the walk with the chosen shot.
    game = _FakeGame()
    off = _lineup(PG=_FakePlayer("pg"))
    skel = _skeleton({"PG": "key"}, {"PG": "upper wing"})
    monkeypatch.setattr("BackEnd.engine.motion_read_map.build_motion_read_map", lambda *a, **k: {})
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot",
                        lambda *a, **k: {"shooter_pos": "PG", "shot_type": "outside",
                                         "via_pass": False, "hot_read": False})
    res = _resolve_motion_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    assert res is not None and res["shooter_pos"] == "PG" and res["shot_type"] == "outside"
    assert res["skeleton"]["steps"][-1]["pos_actions"]["PG"]["action"] == "shoot"


def test_post_subtle_shoot_fires_after_beat(monkeypatch):
    # should_shoot returns None at the per-step check (→ movement = subtle beat), then fires on
    # the post-subtle check → the shot lands AFTER the inserted beat.
    game = _FakeGame()
    off = _lineup(PG=_FakePlayer("pg"))
    skel = _skeleton({"PG": "key"}, {"PG": "key"}, {"PG": "basketSpot"})
    monkeypatch.setattr("BackEnd.engine.motion_read_map.build_motion_read_map", lambda *a, **k: {})
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.decide_step_action",
                        lambda *a, **k: {"action": "SUBTLE_MOVEMENT"})
    calls = {"n": 0}

    def fake_shoot(*a, **k):
        calls["n"] += 1
        return None if calls["n"] == 1 else {"shooter_pos": "PG", "shot_type": "inside",
                                             "via_pass": False, "hot_read": False}

    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot", fake_shoot)
    res = _resolve_motion_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    assert res is not None and res["shooter_pos"] == "PG"
    out = res["skeleton"]["steps"]
    assert any("_subtle_movement" in s for s in out)            # a beat was inserted
    assert out[-1]["pos_actions"]["PG"]["action"] == "shoot"     # then the post-subtle shot


# ---------------------------------------------------------------- handoff

def test_execute_inside_shot_appends_shoot_step():
    game = _FakeGame()
    bh = _FakePlayer("bh")
    off = _lineup(PG=bh)
    steps = _skeleton({"PG": "key"}, {"PG": "basketSpot"}, {"PG": "midLane"})["steps"]
    decision = {"action": "SHOOT", "shooter_pos": "PG", "shot_type": "inside"}
    res = _execute_motion_decision({"steps": steps}, steps[:2], steps[1], "PG", "basketSpot", decision,
                                   game, off, {"PG": _FakePlayer("d")}, is_away_offense=False)
    assert res["shooter_pos"] == "PG" and res["shot_type"] == "inside" and res["playcall"] == "Inside"
    last = res["skeleton"]["steps"][-1]
    assert last["pos_actions"]["PG"]["action"] == "shoot"
    assert len(res["skeleton"]["steps"]) == 3  # base [0,1] + shoot


def test_execute_kickout_appends_pass_then_shoot():
    game = _FakeGame()
    bh, sg = _FakePlayer("bh"), _FakePlayer("sg")
    off = _lineup(PG=bh, SG=sg)
    steps = _skeleton({"PG": "key", "SG": "upper wing"}, {"PG": "key", "SG": "upper wing"})["steps"]
    decision = {"action": "KICKOUT_SHOOT", "shooter_pos": "SG", "shot_type": "outside"}
    res = _execute_motion_decision({"steps": steps}, steps[:2], steps[1], "PG", "key", decision,
                                   game, off, {}, is_away_offense=False)
    assert res["shooter_pos"] == "SG" and res["shooter"] is sg
    actions = [list(s["pos_actions"].values())[0]["action"] for s in res["skeleton"]["steps"][-2:]]
    # second-to-last has pass/receive; last is shoot
    assert res["skeleton"]["steps"][-1]["pos_actions"]["SG"]["action"] == "shoot"
    assert "pass" in [a for s in res["skeleton"]["steps"] for a in
                      (v.get("action") for v in s["pos_actions"].values())]


def test_execute_attack_reuses_drive_sequence(monkeypatch):
    game = _FakeGame()
    bh = _FakePlayer("bh")
    off = _lineup(PG=bh)
    steps = _skeleton({"PG": "upper wing"}, {"PG": "upper wing"})["steps"]
    canned = {
        "steps": [_step({"PG": "midLane"})],
        "shooter": bh, "shooter_pos": "PG", "shooter_location": "midLane",
        "resolved_shot_type": "attack", "playcall": "Attack",
        "motion_attack_uncontested": True, "motion_attack_geometry_contest": True,
        "motion_attack_defense_bonus": 100, "motion_attack_driver_shoots": True,
    }
    monkeypatch.setattr(PR, "_create_attack_drive_shoot_steps", lambda *a, **k: canned)
    decision = {"action": "HOT_READ_SHOOT", "shooter_pos": "PG", "shot_type": "attack", "via_pass": False}
    res = _execute_motion_decision({"steps": steps}, steps[:2], steps[1], "PG", "upper wing", decision,
                                   game, off, {}, is_away_offense=False)
    assert res["shot_type"] == "attack" and res["playcall"] == "Attack"
    assert res["motion_attack_uncontested"] is True and res["motion_attack_defense_bonus"] == 100


# ---------------------------------------------------------------- walk

def test_walk_picks_first_shot_decision(monkeypatch):
    game = _FakeGame()
    bh = _FakePlayer("bh")
    off = _lineup(PG=bh)
    game.offense_team.lineup = off
    skel = _skeleton({"PG": "key"}, {"PG": "key"}, {"PG": "basketSpot"}, {"PG": "key"})

    calls = {"n": 0}

    def fake_decide(*a, **k):
        calls["n"] += 1
        # ADVANCE on step 1, SHOOT on step 2, never reached after
        return {"action": "SHOOT", "shooter_pos": "PG", "shot_type": "inside"} if calls["n"] == 2 else {"action": "ADVANCE"}

    monkeypatch.setattr("BackEnd.engine.motion_step_decision.decide_step_action", fake_decide)
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot", lambda *a, **k: None)
    monkeypatch.setattr("BackEnd.engine.motion_read_map.build_motion_read_map", lambda *a, **k: {})
    res = _resolve_motion_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    assert res is not None and res["shooter_pos"] == "PG"
    # shot fired at step index 2 → truncated [0,1,2] (3) + shoot (1) = 4
    assert len(res["skeleton"]["steps"]) == 4
    assert res["skeleton"]["steps"][-1]["pos_actions"]["PG"]["action"] == "shoot"


def test_walk_weaves_subtle_beat_then_resumes_and_shoots(monkeypatch):
    game = _FakeGame()
    bh = _FakePlayer("bh")
    off = _lineup(PG=bh)
    skel = _skeleton({"PG": "key"}, {"PG": "key"}, {"PG": "basketSpot"})

    calls = {"n": 0}

    def fake_decide(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"action": "SUBTLE_MOVEMENT"}            # step 1 → insert a beat, continue
        return {"action": "SHOOT", "shooter_pos": "PG", "shot_type": "inside"}  # step 2 → shoot

    monkeypatch.setattr("BackEnd.engine.motion_step_decision.decide_step_action", fake_decide)
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot", lambda *a, **k: None)
    monkeypatch.setattr("BackEnd.engine.motion_read_map.build_motion_read_map", lambda *a, **k: {})
    res = _resolve_motion_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    out = res["skeleton"]["steps"]
    # [step0, step1, subtle_beat, step2, shoot]
    assert len(out) == 5
    assert "_subtle_movement" in out[2]                    # beat inserted after step 1
    assert out[3]["pos_actions"]["PG"]["location"] == "basketSpot"  # skeleton resumed at step 2
    assert out[-1]["pos_actions"]["PG"]["action"] == "shoot"


def test_bh_at_step_prefers_receiver_over_passer():
    # A pass step holds both pass (passer) and receive (receiver). The ball handler going forward
    # is the RECEIVER — picking the passer would double a subsequent dish (the reported bug).
    from BackEnd.engine.phase_resolution import _motion_bh_at_step
    step = {"pos_actions": {
        "PG": {"location": "key", "action": "pass"},
        "SG": {"location": "upper wing", "action": "receive"},
        "SF": {"location": "lower wing", "action": "stationary"},
    }}
    pos, loc = _motion_bh_at_step(step)
    assert pos == "SG" and loc == "upper wing"


def test_bh_at_step_handle_ball_when_no_pass():
    from BackEnd.engine.phase_resolution import _motion_bh_at_step
    step = {"pos_actions": {"PG": {"location": "key", "action": "handle_ball"},
                            "SG": {"location": "wing", "action": "stationary"}}}
    assert _motion_bh_at_step(step) == ("PG", "key")


def test_hot_read_stamps_vo_on_initiation_step(monkeypatch):
    # The VO is currently disabled (HOT_READ_VO_ENABLED=False); flip it on to verify the
    # stamping pipeline is intact for when it's re-enabled.
    from BackEnd.engine.phase_resolution import _execute_motion_decision, HOT_READ_VO_FILES
    monkeypatch.setattr(PR, "HOT_READ_VO_ENABLED", True)
    game = _FakeGame()
    bh = _FakePlayer("bh")
    off = _lineup(PG=bh)
    steps = _skeleton({"PG": "upper wing"}, {"PG": "upper wing"})["steps"]
    decision = {"action": "HOT_READ_SHOOT", "shooter_pos": "PG", "shot_type": "outside", "via_pass": False}
    res = _execute_motion_decision({"steps": steps}, steps[:2], steps[1], "PG", "upper wing", decision,
                                   game, off, {}, is_away_offense=False)
    out = res["skeleton"]["steps"]
    appended = out[2:]  # everything after base_steps[:2] is the appended hot-read shot break
    assert appended and appended[0].get("_hot_read_sfx") in HOT_READ_VO_FILES
    assert "hot_read" not in res  # no top-level turn flag anymore (SFX rides the step)


def test_hot_read_vo_disabled_by_default():
    # With HOT_READ_VO_ENABLED False (default), no clip is stamped on the hot-read step.
    from BackEnd.engine.phase_resolution import _execute_motion_decision
    assert PR.HOT_READ_VO_ENABLED is False
    game = _FakeGame()
    off = _lineup(PG=_FakePlayer("bh"))
    steps = _skeleton({"PG": "upper wing"}, {"PG": "upper wing"})["steps"]
    decision = {"action": "HOT_READ_SHOOT", "shooter_pos": "PG", "shot_type": "outside", "via_pass": False}
    res = _execute_motion_decision({"steps": steps}, steps[:2], steps[1], "PG", "upper wing", decision,
                                   game, off, {}, is_away_offense=False)
    assert all("_hot_read_sfx" not in s for s in res["skeleton"]["steps"])


def test_non_hot_read_shot_has_no_vo():
    from BackEnd.engine.phase_resolution import _execute_motion_decision
    game = _FakeGame()
    bh = _FakePlayer("bh")
    off = _lineup(PG=bh)
    steps = _skeleton({"PG": "basketSpot"}, {"PG": "basketSpot"})["steps"]
    decision = {"action": "SHOOT", "shooter_pos": "PG", "shot_type": "inside"}
    res = _execute_motion_decision({"steps": steps}, steps[:2], steps[1], "PG", "basketSpot", decision,
                                   game, off, {}, is_away_offense=False)
    assert "hot_read" not in res
    assert all("_hot_read_sfx" not in s for s in res["skeleton"]["steps"])


def test_freelance_forced_enters_loop_and_shoots(monkeypatch):
    from BackEnd.engine.phase_resolution import _resolve_freelance
    game = _FakeGame(shot_clock=30)
    bh = _FakePlayer("bh")
    off = _lineup(PG=bh, SG=_FakePlayer("sg"))
    skel = _skeleton({"PG": "key", "SG": "upper wing"}, {"PG": "key", "SG": "upper wing"})
    base = skel["steps"][:2]

    # rng that never triggers an early shot (forces the cap path) but holds (no pass) each cycle.
    class _Rng:
        def random(self): return 0.99           # >FREELANCE_PASS_PROB → hold; also non-BH gate → hold
        def randint(self, a, b): return 1        # low → never beats threshold until forced cap
        def choice(self, seq): return list(seq)[0]

    res = _resolve_freelance(skel, base, skel["steps"][1], "PG", game, off, {}, False, _Rng())
    assert res is not None
    out = res["skeleton"]["steps"]
    assert out[-1]["pos_actions"]["PG"]["action"] == "shoot"     # terminated in a shot
    # exactly FREELANCE_MAX_CYCLES movement beats (held every cycle) + the forced shoot
    from BackEnd.engine.motion_freelance import FREELANCE_MAX_CYCLES
    beats = [s for s in out if "_freelance" in s]
    assert len(beats) == FREELANCE_MAX_CYCLES


def test_freelance_pass_transfers_ball_to_receiver():
    from BackEnd.engine.phase_resolution import _resolve_freelance
    game = _FakeGame(shot_clock=30)
    off = _lineup(PG=_FakePlayer("pg"), SG=_FakePlayer("sg"))
    # SG starts near the BH so it stays within the 20-grid pass radius after nudges.
    skel = _skeleton({"PG": "key", "SG": "upper midWing"}, {"PG": "key", "SG": "upper midWing"})

    # Cycle 1: roll low → don't shoot → pass (random<0.80) to SG. Cycle 2: roll high → SG shoots.
    class _Rng:
        def __init__(self): self.cycle_rolls = [1, 200]; self.i = 0
        def random(self): return 0.1            # <0.5 subtle nudge; <0.80 pass
        def randint(self, a, b):
            if (a, b) == (1, 100):
                v = self.cycle_rolls[min(self.i, len(self.cycle_rolls) - 1)]; self.i += 1; return v
            return 2                            # nudge magnitude
        def choice(self, seq): return list(seq)[0]

    res = _resolve_freelance(skel, skel["steps"][:2], skel["steps"][1], "PG", game, off, {}, False, _Rng())
    out = res["skeleton"]["steps"]
    assert any(any(v.get("action") == "pass" for v in s["pos_actions"].values()) for s in out)
    assert res["shooter_pos"] == "SG"           # possession transferred to the pass receiver


def test_walk_no_shot_forces_terminal_shot(monkeypatch):
    game = _FakeGame()
    bh = _FakePlayer("bh")
    off = _lineup(PG=bh)
    skel = _skeleton({"PG": "key"}, {"PG": "key"}, {"PG": "basketSpot"})

    monkeypatch.setattr("BackEnd.engine.motion_step_decision.decide_step_action",
                        lambda *a, **k: {"action": "ADVANCE"})
    monkeypatch.setattr("BackEnd.engine.motion_read_map.build_motion_read_map", lambda *a, **k: {})
    res = _resolve_motion_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    assert res is not None and res["shooter_pos"] == "PG"
    # forced at last step (index 2, basketSpot → inside)
    assert res["shot_type"] == "inside"
    assert res["skeleton"]["steps"][-1]["pos_actions"]["PG"]["action"] == "shoot"
