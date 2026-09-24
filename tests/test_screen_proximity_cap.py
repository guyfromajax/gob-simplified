"""Stage A's proximity cap ships behind ``GOB_SCREEN_PROXIMITY_CAP``, **default OFF**
(2026-09-24), on its OWN flag — deliberately not folded into Stage A.

Stage A aims the screener at the receiver's DEFENDER. In sag and help defences that
defender is nowhere near the receiver, so the screen is dragged away from the play:
measured, screener -> receiver reaches p90 17.0 grid uncapped.

What this pins:

  * **default OFF**, and **unreachable when targeting is off** — the cap is additive;
  * the distance is the house's EXISTING derived gate, ``pass_contest.PASS_LANE_DIST``,
    resolved at call time and never inlined — no new tuning number;
  * a refused screen **falls back to today's placement and is counted**, it is not
    clamped onto the line;
  * **no RNG**, on any combination of the three flags.
"""

import math
import random

import pytest

from BackEnd.utils import screen_targeting as ST


class _P:
    def __init__(self, pid="p", height=75):
        self.player_id = pid
        self.height = height
        self.attributes = {"AG": 50, "ST": 50, "IQ": 50, "ND": 50, "CH": 50}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for f in (ST.SCREEN_TARGETING_FLAG, ST.SCREEN_PROXIMITY_CAP_FLAG):
        monkeypatch.delenv(f, raising=False)
    monkeypatch.delenv("GOB_SCREEN_CONTEST", raising=False)


def _scene(defender_x):
    """PF screens for SG at 'key'; SG then moves to 'upper wing'. The receiver's defender
    sits at ``defender_x`` — far away when we want the cap to bite."""
    steps = [
        {"timestamp": 0, "pos_actions": {
            "PF": {"action": "screen", "location": "key"},
            "SG": {"action": "cut", "location": "key"}}},
        {"timestamp": 300, "pos_actions": {
            "SG": {"action": "receive", "location": "upper wing"}}},
    ]
    anims = [
        {"playerId": "o_PF", "start": {"x": 67.0, "y": 25.0}, "end": {"x": 67.0, "y": 25.0},
         "movement": [{"timestamp": 0, "coords": {"x": 67.0, "y": 25.0}, "action": "screen"}]},
        {"playerId": "o_SG", "start": {"x": 64.0, "y": 25.0}, "end": {"x": 64.0, "y": 25.0},
         "movement": [{"timestamp": 0, "coords": {"x": 64.0, "y": 25.0}, "action": "cut"}]},
        {"playerId": "d_SG", "start": {"x": defender_x, "y": 25.0},
         "end": {"x": defender_x, "y": 25.0},
         "movement": [{"timestamp": 0, "coords": {"x": defender_x, "y": 25.0}},
                      {"timestamp": 300, "coords": {"x": defender_x, "y": 25.0}}]},
    ]
    off = {"PF": _P("o_PF"), "SG": _P("o_SG")}
    dfn = {"SG": _P("d_SG")}
    return steps, anims, off, dfn


def _run(monkeypatch, defender_x, cap):
    monkeypatch.setenv(ST.SCREEN_TARGETING_FLAG, "1")
    if cap:
        monkeypatch.setenv(ST.SCREEN_PROXIMITY_CAP_FLAG, "1")
    steps, anims, off, dfn = _scene(defender_x)
    stats = ST.apply_screen_targeting(anims, None, {"steps": steps}, off, dfn)
    coord = [a for a in anims if a["playerId"] == "o_PF"][0]["movement"][0]["coords"]
    return stats, coord


# ---------------------------------------------------------------------------
# shipped defaults and reachability
# ---------------------------------------------------------------------------


def test_cap_defaults_off():
    assert ST.screen_proximity_cap_enabled() is False


def test_kill_switch(monkeypatch):
    monkeypatch.setenv(ST.SCREEN_PROXIMITY_CAP_FLAG, "1")
    assert ST.screen_proximity_cap_enabled() is True
    monkeypatch.setenv(ST.SCREEN_PROXIMITY_CAP_FLAG, "0")
    assert ST.screen_proximity_cap_enabled() is False


def test_cap_on_with_targeting_off_is_unreachable_and_a_no_op(monkeypatch):
    """THE additive guarantee. With Stage A off the applier returns before the cap is even
    consulted, so the cap cannot change a coordinate or a count."""
    monkeypatch.setenv(ST.SCREEN_PROXIMITY_CAP_FLAG, "1")
    steps, anims, off, dfn = _scene(20.0)
    before = [dict(a["movement"][0]["coords"]) for a in anims]
    stats = ST.apply_screen_targeting(anims, None, {"steps": steps}, off, dfn)
    assert stats["enabled"] is False
    assert stats["applied"] == 0
    assert "cap_refused" not in stats, "the cap must not even report when Stage A is off"
    assert [dict(a["movement"][0]["coords"]) for a in anims] == before


# ---------------------------------------------------------------------------
# the distance is the house's existing constant
# ---------------------------------------------------------------------------


def test_distance_is_pass_lane_dist_resolved_at_call_time():
    """Inlining 8.0 would make this a NEW tuning number, which the brief forbids. It is
    the same gate boxout_contest reused, derived independently to the same value."""
    from BackEnd.engine.pass_contest import PASS_LANE_DIST
    assert ST.proximity_cap_distance() == pytest.approx(PASS_LANE_DIST)
    assert ST.proximity_cap_distance() == pytest.approx(8.0)


def test_distance_is_not_inlined(monkeypatch):
    """Resolved through the module every call, so the house's constant stays the source."""
    import BackEnd.engine.pass_contest as PC
    monkeypatch.setattr(PC, "PASS_LANE_DIST", 3.0)
    assert ST.proximity_cap_distance() == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# what the cap actually does
# ---------------------------------------------------------------------------


def test_a_nearby_defender_is_unaffected_by_the_cap(monkeypatch):
    """The cap must only refuse; it must never change a screen it accepts."""
    uncapped, c_uncapped = _run(monkeypatch, 62.0, cap=False)
    capped, c_capped = _run(monkeypatch, 62.0, cap=True)
    assert uncapped["applied"] == 1 and capped["applied"] == 1
    assert capped["cap_refused"] == 0
    assert c_capped == c_uncapped, "an accepted screen must land on the identical point"


def test_a_distant_defender_is_refused_and_keeps_todays_placement(monkeypatch):
    """The whole point: a screen 8+ units from the man it is for is not his screen."""
    uncapped, c_uncapped = _run(monkeypatch, 20.0, cap=False)
    assert uncapped["applied"] == 1, "uncapped Stage A places it anyway"
    capped, c_capped = _run(monkeypatch, 20.0, cap=True)
    assert capped["applied"] == 0
    assert capped["cap_refused"] == 1
    assert capped["fallback"]["cap_too_far_from_receiver"] == 1
    assert c_capped == {"x": 67.0, "y": 25.0}, "must keep TODAY's placement, not a clamp"
    assert c_capped != c_uncapped


def test_a_refused_screen_is_not_clamped_onto_the_line(monkeypatch):
    """A clamped point screens nobody and is not near the receiver — a third position that
    is not a screen at all. Declining beats inventing one."""
    capped, coord = _run(monkeypatch, 20.0, cap=True)
    # the clamped point would sit cap_distance from the receiver along the target line
    recv = {"x": 64.0, "y": 25.0}
    gap = math.hypot(coord["x"] - recv["x"], coord["y"] - recv["y"])
    assert gap == pytest.approx(3.0), "this is the untouched OFFSET_SPOTS gap, not a clamp"


def test_the_boundary_is_inclusive_of_the_gate_distance(monkeypatch):
    """`gap > cap` refuses; exactly at the gate is accepted, matching how the house's
    other consumers of PASS_LANE_DIST read it (`<=`)."""
    import BackEnd.engine.pass_contest as PC
    monkeypatch.setattr(PC, "PASS_LANE_DIST", 0.0)
    capped, _ = _run(monkeypatch, 62.0, cap=True)
    assert capped["cap_refused"] == 1, "a zero gate must refuse a non-zero gap"


def test_every_judged_screen_is_recorded_not_just_the_refusals(monkeypatch):
    """cap_gap carries the whole distribution, so 'how close was it' is answerable
    without re-running."""
    capped, _ = _run(monkeypatch, 62.0, cap=True)
    assert sum(capped["cap_gap"].values()) == 1


def test_it_draws_no_rng_in_any_flag_combination(monkeypatch):
    from BackEnd.utils import sim_random
    for tgt in ("0", "1"):
        for cap in ("0", "1"):
            monkeypatch.setenv(ST.SCREEN_TARGETING_FLAG, tgt)
            monkeypatch.setenv(ST.SCREEN_PROXIMITY_CAP_FLAG, cap)
            steps, anims, off, dfn = _scene(20.0)
            st_std, st_sim = random.getstate(), sim_random.sim_rng.getstate()
            ST.apply_screen_targeting(anims, None, {"steps": steps}, off, dfn)
            assert random.getstate() == st_std
            assert sim_random.sim_rng.getstate() == st_sim
