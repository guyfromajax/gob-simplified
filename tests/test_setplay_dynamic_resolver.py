"""Dynamic HCO Set Plays — Stage B/C: the per-step set-play resolver
(`_resolve_setplay_offense_shot_dynamic`). These isolate the SET-PLAY-specific behaviour vs the
motion resolver: (1) the offense never proactively subtle-moves (`offense_reads` forced False), so
the offense only leaves the skeleton when the DEFENSE forces it; (2) after a defense-forced subtle
the BH either re-enters the skeleton (`_setplay_recovery_roll` True) or is forced into freelance
(False). The universal `should_shoot` hot read still runs every step.

The inner helpers (read map, should_shoot, decide_step_action, recovery roll, freelance) are
monkeypatched so these test the WALK + the forced-subtle progression, not the contests themselves.
"""
import random
import BackEnd.engine.phase_resolution as PR
from BackEnd.engine.phase_resolution import _resolve_hco_offense_shot_dynamic


# The `_resolve_setplay_offense_shot_dynamic` thin delegate was removed (cleanup 2026-07-13) — all HCO
# shot resolution calls the unified `_resolve_hco_offense_shot_dynamic` directly. Local shim keeps the
# set-play tests below unchanged (is_setplay=True).
def _resolve_setplay_offense_shot_dynamic(skeleton, game, off_lineup, def_lineup):
    return _resolve_hco_offense_shot_dynamic(skeleton, game, off_lineup, def_lineup, is_setplay=True)

_ATTR_KEYS = ["SC", "ST", "AG", "SH", "ID", "OD", "IQ", "CH"]


class _FakePlayer:
    def __init__(self, pid, **overrides):
        self.player_id = pid
        self.attributes = {k: 50 for k in _ATTR_KEYS}
        self.attributes.update(overrides)


class _FakeTeam:
    def __init__(self, team_id, aggression=4):
        self.team_id = team_id
        self.is_user_team = False
        self.team_attributes = {
            "discipline": 0, "fight": 0, "offensive_efficiency": 0,
            "defensive_efficiency": 0, "team_chemistry": 7,
        }
        self.strategy_calls = {"aggression_call": "normal", "tempo_call": "normal"}
        # aggression 4 → defense_pressure roll (0-4 <= 4) always True when rolls aren't pinned.
        self.strategy_settings = {"aggression": aggression}


class _FakeGame:
    def __init__(self, defense_playcall="Man", shot_clock=30, def_aggression=4):
        self.home_team = _FakeTeam("HOME")
        self.away_team = _FakeTeam("AWAY", aggression=def_aggression)
        self.offense_team = self.home_team
        self.defense_team = self.away_team
        self.game_state = {"defense_playcall": defense_playcall, "shot_clock_remaining": shot_clock}


def _step(locations, ts=0):
    return {"timestamp": ts,
            "pos_actions": {p: {"location": loc, "action": "handle_ball"} for p, loc in locations.items()},
            "events": []}


def _skeleton(*step_locs):
    return {"steps": [_step(loc, ts=i * 1000) for i, loc in enumerate(step_locs)]}


def _patch_common(monkeypatch):
    """Neutralise the per-step contest helpers that need real game/defender context."""
    monkeypatch.setattr("BackEnd.engine.motion_read_map.build_motion_read_map", lambda *a, **k: {})
    monkeypatch.setattr(PR, "_hco_pass_lane_dist", lambda *a, **k: 100.0)
    monkeypatch.setattr(PR, "_hco_blocked_dish_targets", lambda *a, **k: set())
    monkeypatch.setattr(PR, "_roll_subtle_defender_reads", lambda *a, **k: {})


# --------------------------------------------------------- offense never proactively reads

def test_offense_reads_forced_false(monkeypatch):
    # The defining set-play difference: decide_step_action is ALWAYS handed offense_reads=False,
    # so the offense never subtle-moves on its own — only a defense-forced disruption can.
    _patch_common(monkeypatch)
    seen = {}

    def fake_decide(*a, **k):
        seen.update(k)
        return {"action": "ADVANCE"}

    monkeypatch.setattr("BackEnd.engine.motion_step_decision.decide_step_action", fake_decide)
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot", lambda *a, **k: None)
    game = _FakeGame(def_aggression=4)
    monkeypatch.setattr(random, "randint", lambda a, b: a)  # (0,4)->0 <=4 → defense_pressure True
    off = {"PG": _FakePlayer("pg")}
    # end inside so the end-of-walk forced shot is a plain inside shot (no attack-drive geometry).
    skel = _skeleton({"PG": "key"}, {"PG": "basketSpot"})
    _resolve_setplay_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    assert seen.get("offense_reads") is False
    assert seen.get("defense_pressure") is True


def test_no_pressure_walks_static_skeleton_to_forced_shot(monkeypatch):
    # aggression 0 + max roll → defense not pressuring. Offense never reads → NO subtle beats;
    # the walk just advances and forces a terminal shot at the last step.
    _patch_common(monkeypatch)
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot", lambda *a, **k: None)
    game = _FakeGame(def_aggression=0)
    monkeypatch.setattr(random, "randint", lambda a, b: b)  # (0,4)->4 <=0 → defense_pressure False
    off = {"PG": _FakePlayer("pg")}
    skel = _skeleton({"PG": "key"}, {"PG": "key"}, {"PG": "basketSpot"})
    res = _resolve_setplay_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    out = res["skeleton"]["steps"]
    assert all("_subtle_movement" not in s for s in out)            # offense never moved on its own
    assert out[-1]["pos_actions"]["PG"]["action"] == "shoot"        # terminal forced shot


# --------------------------------------------------------- universal hot read

def test_universal_should_shoot_fires_per_step(monkeypatch):
    # should_shoot runs every step (not only after a forced subtle) and terminates the walk.
    _patch_common(monkeypatch)
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot",
                        lambda *a, **k: {"shooter_pos": "PG", "shot_type": "outside",
                                         "via_pass": False, "hot_read": True})
    game = _FakeGame()
    off = {"PG": _FakePlayer("pg")}
    skel = _skeleton({"PG": "key"}, {"PG": "upper wing"})
    res = _resolve_setplay_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    assert res["shooter_pos"] == "PG" and res["shot_type"] == "outside"
    assert res["skeleton"]["steps"][-1]["pos_actions"]["PG"]["action"] == "shoot"


# --------------------------------------------------------- forced-subtle progression

def _subtle_then_advance(monkeypatch):
    """decide_step_action: SUBTLE on the first call, ADVANCE after."""
    calls = {"n": 0}

    def fake_decide(*a, **k):
        calls["n"] += 1
        return {"action": "SUBTLE_MOVEMENT"} if calls["n"] == 1 else {"action": "ADVANCE"}

    monkeypatch.setattr("BackEnd.engine.motion_step_decision.decide_step_action", fake_decide)


def test_post_subtle_recovery_reenters_skeleton(monkeypatch):
    # Defense forces a subtle, BH doesn't shoot post-beat, recovery roll WON → re-enter the
    # skeleton (continue the walk) → no freelance; ends in the terminal forced shot.
    _patch_common(monkeypatch)
    _subtle_then_advance(monkeypatch)
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot", lambda *a, **k: None)
    monkeypatch.setattr(PR, "_setplay_recovery_roll", lambda *a, **k: True)
    freelanced = {"hit": False}
    monkeypatch.setattr(PR, "_resolve_freelance", lambda *a, **k: freelanced.update(hit=True))
    game = _FakeGame(def_aggression=4)
    monkeypatch.setattr(random, "randint", lambda a, b: a)  # pressure True; small subtle elapsed
    off = {"PG": _FakePlayer("pg")}
    skel = _skeleton({"PG": "key"}, {"PG": "key"}, {"PG": "basketSpot"})
    res = _resolve_setplay_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    out = res["skeleton"]["steps"]
    assert any("_subtle_movement" in s for s in out)               # a forced subtle happened
    assert freelanced["hit"] is False                              # recovery won → NOT freelance
    assert out[-1]["pos_actions"]["PG"]["action"] == "shoot"


def test_post_subtle_recovery_lost_goes_freelance(monkeypatch):
    # Same forced subtle, but recovery roll LOST → forced freelance (_resolve_freelance result
    # is returned verbatim).
    _patch_common(monkeypatch)
    _subtle_then_advance(monkeypatch)
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot", lambda *a, **k: None)
    monkeypatch.setattr(PR, "_setplay_recovery_roll", lambda *a, **k: False)
    sentinel = {"skeleton": {"steps": []}, "shooter_pos": "FREELANCE", "shot_type": "inside"}
    monkeypatch.setattr(PR, "_resolve_freelance", lambda *a, **k: sentinel)
    game = _FakeGame(def_aggression=4)
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    off = {"PG": _FakePlayer("pg")}
    skel = _skeleton({"PG": "key"}, {"PG": "key"}, {"PG": "basketSpot"})
    res = _resolve_setplay_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    assert res is sentinel


def test_post_subtle_shot_fires_after_beat(monkeypatch):
    # should_shoot None on the per-step check (→ subtle), then fires on the post-subtle check →
    # the shot lands AFTER the inserted beat (recovery roll never reached).
    _patch_common(monkeypatch)
    _subtle_then_advance(monkeypatch)
    calls = {"n": 0}

    def fake_shoot(*a, **k):
        calls["n"] += 1
        return None if calls["n"] == 1 else {"shooter_pos": "PG", "shot_type": "inside",
                                             "via_pass": False, "hot_read": False}

    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot", fake_shoot)
    monkeypatch.setattr(PR, "_setplay_recovery_roll",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("recovery should not run")))
    game = _FakeGame(def_aggression=4)
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    off = {"PG": _FakePlayer("pg")}
    skel = _skeleton({"PG": "key"}, {"PG": "key"}, {"PG": "basketSpot"})
    res = _resolve_setplay_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    out = res["skeleton"]["steps"]
    assert any("_subtle_movement" in s for s in out)
    assert out[-1]["pos_actions"]["PG"]["action"] == "shoot"


def test_freelance_forced_direct_goes_freelance(monkeypatch):
    # Defense knocks the BH straight out (disruption → FREELANCE_FORCED, no subtle) → freelance.
    _patch_common(monkeypatch)
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.decide_step_action",
                        lambda *a, **k: {"action": "FREELANCE_FORCED"})
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot", lambda *a, **k: None)
    sentinel = {"skeleton": {"steps": []}, "shooter_pos": "FREELANCE"}
    monkeypatch.setattr(PR, "_resolve_freelance", lambda *a, **k: sentinel)
    game = _FakeGame(def_aggression=4)
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    off = {"PG": _FakePlayer("pg")}
    skel = _skeleton({"PG": "key"}, {"PG": "key"})
    res = _resolve_setplay_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    assert res is sentinel


def test_subtle_forced_shot_when_clock_expiring(monkeypatch):
    # Shot-clock backstop (same as motion): finishing the forced subtle would leave < 1s → the BH
    # is forced to shoot with a hard penalty rather than holding for the recovery roll.
    _patch_common(monkeypatch)
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.decide_step_action",
                        lambda *a, **k: {"action": "SUBTLE_MOVEMENT"})
    monkeypatch.setattr("BackEnd.engine.motion_step_decision.should_shoot", lambda *a, **k: None)
    monkeypatch.setattr(PR, "_estimate_step_game_seconds", lambda *a, **k: 0.0)
    monkeypatch.setattr(PR, "_setplay_recovery_roll",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("backstop should pre-empt recovery")))

    # (0,4) pressure roll → 0 (True); the subtle elapsed roll (3,5) → 5 → 2 - 5 < 1 → backstop.
    def fake_randint(a, b):
        return 0 if (a, b) == (0, 4) else 5

    monkeypatch.setattr(random, "randint", fake_randint)
    game = _FakeGame(def_aggression=4, shot_clock=2)
    off = {"PG": _FakePlayer("pg")}
    skel = _skeleton({"PG": "basketSpot"}, {"PG": "basketSpot"})
    res = _resolve_setplay_offense_shot_dynamic(skel, game, off, {"PG": _FakePlayer("d")})
    assert res["forced_shot_penalty"] > 0
    assert res["skeleton"]["steps"][-1]["pos_actions"]["PG"]["action"] == "shoot"


def test_malformed_skeleton_defers(monkeypatch):
    # < 2 steps → defer to the standard set-play path (None).
    _patch_common(monkeypatch)
    game = _FakeGame()
    assert _resolve_setplay_offense_shot_dynamic(_skeleton({"PG": "key"}), game,
                                                 {"PG": _FakePlayer("pg")}, {"PG": _FakePlayer("d")}) is None
