"""Dynamic HCO §4 passing lanes — Stage 1 (man defense): the hot-read 'truly open' decision gate.
Covers the pure lane geometry (defenders_in_lane), the per-game aggression lane distance
(_hco_pass_lane_dist), and the man-defense blocked-dish reconstruction (_hco_blocked_dish_targets)."""
import random
import BackEnd.engine.phase_resolution as PR
from BackEnd.engine.pass_contest import defenders_in_lane


class _P:
    def __init__(self, pid):
        self.player_id = pid


class _Team:
    def __init__(self, aggression_call="normal"):
        self.strategy_calls = {"aggression_call": aggression_call}


class _Game:
    def __init__(self, aggression_call="normal"):
        self.game_state = {}
        self.defense_team = _Team(aggression_call)


# ---------------------------------------------------------------- defenders_in_lane (geometry)

def test_midlane_defender_caught_endpoints_and_far_excluded():
    dc = {"mid": {"x": 30, "y": 27},        # perp 2, t≈0.5 → in lane
          "passer_man": {"x": 1, "y": 25},   # t≈0 → excluded by band
          "recv_man": {"x": 59, "y": 25},    # t≈1 → excluded by band
          "far": {"x": 30, "y": 40}}         # perp 15 → excluded by distance
    assert defenders_in_lane({"x": 0, "y": 25}, {"x": 60, "y": 25}, dc, 6.0) == {"mid"}


def test_distance_gate():
    dc = {"mid": {"x": 30, "y": 27}}  # perp 2
    assert defenders_in_lane({"x": 0, "y": 25}, {"x": 60, "y": 25}, dc, 1.0) == set()
    assert defenders_in_lane({"x": 0, "y": 25}, {"x": 60, "y": 25}, dc, 6.0) == {"mid"}


def test_exclude_set_skips_ids():
    dc = {"mid": {"x": 30, "y": 27}}
    assert defenders_in_lane({"x": 0, "y": 25}, {"x": 60, "y": 25}, dc, 6.0, exclude={"mid"}) == set()


# ---------------------------------------------------------------- _hco_pass_lane_dist

def test_lane_dist_passive_and_aggressive_are_fixed():
    assert PR._hco_pass_lane_dist(_Game("passive")) == 6.0
    assert PR._hco_pass_lane_dist(_Game("aggressive")) == 5.0


def test_lane_dist_normal_rolled_once_then_cached(monkeypatch):
    monkeypatch.setattr(random, "randint", lambda a, b: 5)
    g = _Game("normal")
    assert PR._hco_pass_lane_dist(g) == 5.0
    assert g.game_state["_hco_pass_lane_dist_normal"] == 5.0
    # A later (different) roll must NOT change the cached per-game value.
    monkeypatch.setattr(random, "randint", lambda a, b: 6)
    assert PR._hco_pass_lane_dist(g) == 5.0


# ---------------------------------------------------------------- _hco_blocked_dish_targets (man)

_OFF = {"PG": _P("o_pg"), "SG": _P("o_sg"), "SF": _P("o_sf")}
_DEF = {"PG": _P("d_pg"), "SG": _P("d_sg"), "SF": _P("d_sf")}
_O2D = {"PG": "PG", "SG": "SG", "SF": "SF"}


def _step():
    return {"pos_actions": {
        "PG": {"location": "key", "coords": {"x": 0, "y": 25}, "action": "handle_ball"},
        "SG": {"location": "upper wing", "coords": {"x": 60, "y": 25}},
        "SF": {"location": "lower wing", "coords": {"x": 30, "y": 5}},
    }}


def test_blocked_when_help_defender_sits_in_dish_lane(monkeypatch):
    # SF's man sags to (30,25) — dead in the PG→SG lane → SG is not "truly open".
    def fake_gdc(off_coords, *a, **k):
        if abs(off_coords["x"] - 30) < 1 and abs(off_coords["y"] - 5) < 1:
            return {"x": 30, "y": 25}        # SF's defender sags mid-lane
        return {"x": off_coords["x"], "y": off_coords["y"]}  # others sit on their man
    monkeypatch.setattr("BackEnd.utils.shared_defense.get_defender_coords", fake_gdc)
    blocked = PR._hco_blocked_dish_targets(_step(), "PG", _OFF, _DEF, _O2D, False, "normal", 6.0)
    assert "SG" in blocked


def test_clear_when_all_defenders_sit_on_their_men(monkeypatch):
    monkeypatch.setattr("BackEnd.utils.shared_defense.get_defender_coords",
                        lambda oc, *a, **k: {"x": oc["x"], "y": oc["y"]})
    blocked = PR._hco_blocked_dish_targets(_step(), "PG", _OFF, _DEF, _O2D, False, "normal", 6.0)
    assert blocked == set()


# ---------------------------------------------------------------- _hco_blocked_dish_targets (zone)

def test_zone_blocked_when_zone_defender_sits_in_lane(monkeypatch):
    # Zone def coords come from assign_all_zone_defenders (home orientation). Place a zone defender
    # mid-lane (30,25) of the PG→SG line → SG covered. Home offense → no flip.
    monkeypatch.setattr(
        "BackEnd.utils.shared_defense.assign_all_zone_defenders",
        lambda *a, **k: ({"C": {"x": 30, "y": 25}, "PG": {"x": 2, "y": 25}}, {}),
    )
    monkeypatch.setattr(
        "BackEnd.engine.attack_drive_clearance._zone_boundaries_for_spot",
        lambda *a, **k: {"C": [(0, 0)], "PG": [(0, 0)]},
    )
    blocked = PR._hco_blocked_dish_targets(
        _step(), "PG", _OFF, _DEF, {}, False, "normal", 6.0, zone=True, defense_playcall="2-3 Zone")
    assert "SG" in blocked


def test_zone_clear_when_no_zone_defender_in_lane(monkeypatch):
    monkeypatch.setattr(
        "BackEnd.utils.shared_defense.assign_all_zone_defenders",
        lambda *a, **k: ({"C": {"x": 30, "y": 45}, "PG": {"x": 2, "y": 25}}, {}),  # C far off the lane
    )
    monkeypatch.setattr(
        "BackEnd.engine.attack_drive_clearance._zone_boundaries_for_spot",
        lambda *a, **k: {"C": [(0, 0)], "PG": [(0, 0)]},
    )
    blocked = PR._hco_blocked_dish_targets(
        _step(), "PG", _OFF, _DEF, {}, False, "normal", 6.0, zone=True, defense_playcall="2-3 Zone")
    assert blocked == set()


# ---------------------------------------------------------------- _hco_resolve_dish_contest (Stage 2)

class _PA:  # player with attributes
    def __init__(self, pid, **attrs):
        self.player_id = pid
        self.attributes = {"PS": 50, "CH": 50, "IQ": 50, "OD": 50, "AG": 50}
        self.attributes.update(attrs)


class _OffTeam:
    team_attributes = {"offensive_efficiency": 0}


class _Rng6:
    def randint(self, a, b):
        return min(6, b)


def test_dish_contest_strong_passer_completes(monkeypatch):
    # All defenders sit on their men; an elite passer clears the safety gate → COMPLETE.
    monkeypatch.setattr("BackEnd.utils.shared_defense.get_defender_coords",
                        lambda oc, *a, **k: {"x": oc["x"], "y": oc["y"]})
    off = {"PG": _PA("o_pg", PS=99, CH=99, IQ=99), "SG": _PA("o_sg"), "SF": _PA("o_sf")}
    deff = {"PG": _PA("d_pg"), "SG": _PA("d_sg"), "SF": _PA("d_sf")}
    out = PR._hco_resolve_dish_contest(_step(), "PG", "SG", off, deff, _O2D, False, "normal", 6.0,
                                       False, None, _OffTeam(), _Rng6())
    assert out["outcome"] == "COMPLETE"


def test_dish_contest_weak_passer_lane_defender_intercepts(monkeypatch):
    # A high-OD defender planted mid-lane + a turnover-prone passer → INTERCEPT.
    def fake_gdc(oc, *a, **k):
        if abs(oc["x"] - 30) < 1 and abs(oc["y"] - 5) < 1:
            return {"x": 40, "y": 25}   # SF's man jumps into the PG→SG lane (t≈0.67)
        return {"x": oc["x"], "y": oc["y"]}
    monkeypatch.setattr("BackEnd.utils.shared_defense.get_defender_coords", fake_gdc)
    off = {"PG": _PA("o_pg", PS=3, CH=3, IQ=3), "SG": _PA("o_sg"), "SF": _PA("o_sf")}
    deff = {"PG": _PA("d_pg"), "SG": _PA("d_sg"), "SF": _PA("d_sf", OD=99, CH=99, IQ=99, AG=99)}
    out = PR._hco_resolve_dish_contest(_step(), "PG", "SG", off, deff, _O2D, False, "normal", 6.0,
                                       False, None, _OffTeam(), _Rng6())
    assert out["outcome"] in ("INTERCEPT", "BAT_OOB")


# ---------------------------------------------------------------- min_perp_in_lane (tracking)

def test_min_perp_in_lane_bands():
    from BackEnd.engine.pass_contest import min_perp_in_lane
    dc = {"mid": {"x": 30, "y": 27},        # perp 2, t≈0.5
          "recv_man": {"x": 60, "y": 25},    # perp 0, t=1.0
          "passer_man": {"x": 0, "y": 25},   # t=0 (excluded both bands)
          "far": {"x": 30, "y": 45}}         # perp 20
    p, r = {"x": 0, "y": 25}, {"x": 60, "y": 25}
    assert min_perp_in_lane(p, r, dc, 0.1, 0.9) == 2.0   # mid-lane help only (receiver's man excluded)
    assert min_perp_in_lane(p, r, dc, 0.1, 1.0) == 0.0   # full band includes the receiver's man
    assert min_perp_in_lane(p, r, {"passer_man": {"x": 0, "y": 25}}, 0.1, 0.9) is None
