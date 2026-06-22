"""Phase 4/4b tests — Dynamic HCO Motion subtle-movement beat emission."""
import math
from BackEnd.engine.motion_subtle import build_subtle_beat
from BackEnd.engine.attack_drive_clearance import _spot_display_coords, _basket_display_coords


class _FakePlayer:
    def __init__(self, pid):
        self.player_id = pid


class FakeRng:
    """choice → seq[min(choice_idx, len-1)]; randint → randint_val; random → random_val.

    random_val defaults to 1.0 so non-BH players HOLD unless a test opts them into moving.
    """
    def __init__(self, choice_idx=0, randint_val=3, random_val=1.0):
        self.choice_idx = choice_idx
        self.randint_val = randint_val
        self.random_val = random_val

    def choice(self, seq):
        seq = list(seq)
        return seq[min(self.choice_idx, len(seq) - 1)]

    def randint(self, a, b):
        return min(max(self.randint_val, a), b)

    def random(self):
        return self.random_val


def _step(locations, ts=1000):
    return {"timestamp": ts,
            "pos_actions": {p: {"location": loc, "action": "handle_ball" if p == "PG" else "stationary"}
                            for p, loc in locations.items()},
            "events": []}


def _lineup(*positions):
    return {p: _FakePlayer(p.lower()) for p in positions}


def _disp(loc, away=False):
    c = _spot_display_coords(loc, away)
    return round(c["x"], 1), round(c["y"], 1)


# ---------------------------------------------------------------- BH radial moves

def test_in_place_keeps_bh_coords():
    beat = build_subtle_beat(_step({"PG": "key", "SG": "upper wing"}), _lineup("PG", "SG"),
                             "PG", is_away_offense=False, rng=FakeRng(choice_idx=0))  # in_place
    pg = beat["pos_actions"]["PG"]
    kx, ky = _disp("key")
    assert pg["action"] == "handle_ball" and pg["coords"]["x"] == kx and pg["coords"]["y"] == ky
    assert beat["_subtle_movement"]["bh_move"] == "in_place"


def test_dribble_back_moves_away_from_basket():
    beat = build_subtle_beat(_step({"PG": "key"}), _lineup("PG"),
                             "PG", is_away_offense=False, rng=FakeRng(choice_idx=1, randint_val=4))  # back
    kx, ky = _disp("key")
    basket = _basket_display_coords(False)
    new = beat["pos_actions"]["PG"]["coords"]
    assert abs(new["x"] - basket["x"]) > abs(kx - basket["x"])
    assert 1.5 <= math.hypot(new["x"] - kx, new["y"] - ky) <= 6.5


def test_dribble_in_moves_toward_basket():
    beat = build_subtle_beat(_step({"PG": "key"}), _lineup("PG"),
                             "PG", is_away_offense=False, rng=FakeRng(choice_idx=2, randint_val=4))  # in
    kx, _ = _disp("key")
    basket = _basket_display_coords(False)
    assert abs(beat["pos_actions"]["PG"]["coords"]["x"] - basket["x"]) < abs(kx - basket["x"])


def test_away_offense_uses_away_basket_direction():
    beat = build_subtle_beat(_step({"PG": "key"}), _lineup("PG"),
                             "PG", is_away_offense=True, rng=FakeRng(choice_idx=2, randint_val=4))  # in
    kx, _ = _disp("key", away=True)
    basket = _basket_display_coords(True)
    assert abs(beat["pos_actions"]["PG"]["coords"]["x"] - basket["x"]) < abs(kx - basket["x"])


# ---------------------------------------------------------------- BH side-dribble (4b)

def test_bh_side_dribble_halfway_to_open_neighbor():
    # PG at key (perimeter); neighbors upper/lower midWing are open → side eligible.
    beat = build_subtle_beat(_step({"PG": "key"}), _lineup("PG"),
                             "PG", is_away_offense=False, rng=FakeRng(choice_idx=3))  # idx3 → "side"
    assert beat["_subtle_movement"]["bh_move"] == "side"
    kx, ky = _disp("key")
    new = beat["pos_actions"]["PG"]["coords"]
    # moved off the key but only partway toward a neighbor (a small nudge)
    assert (new["x"], new["y"]) != (kx, ky)
    assert math.hypot(new["x"] - kx, new["y"] - ky) <= 12  # ~half the spot gap


def test_bh_side_dribble_unavailable_inside():
    # basketSpot is inside / not a perimeter spot → "side" never offered.
    beat = build_subtle_beat(_step({"PG": "basketSpot"}), _lineup("PG"),
                             "PG", is_away_offense=False, rng=FakeRng(choice_idx=9))
    assert beat["_subtle_movement"]["bh_move"] != "side"


# ---------------------------------------------------------------- non-BH moves (4b)

def test_non_bh_inside_player_flashes_to_inside_target():
    # C at basketSpot (inside); random_val 0 → moves; choice 0 → flash; first free target = midLane.
    beat = build_subtle_beat(_step({"PG": "key", "C": "basketSpot"}), _lineup("PG", "C"),
                             "PG", is_away_offense=False, rng=FakeRng(choice_idx=0, random_val=0.0))
    c = beat["pos_actions"]["C"]
    assert c["action"] == "cut"
    mx, my = _disp("midLane")
    assert c["coords"]["x"] == mx and c["coords"]["y"] == my
    assert "C" in beat["_subtle_movement"]["movers"]


def test_non_bh_outside_player_slides_to_open_neighbor():
    # SG at upper wing (perimeter); choice 0 → slide; first neighbor = upper midWing.
    beat = build_subtle_beat(_step({"PG": "key", "SG": "upper wing"}), _lineup("PG", "SG"),
                             "PG", is_away_offense=False, rng=FakeRng(choice_idx=0, random_val=0.0))
    sg = beat["pos_actions"]["SG"]
    assert sg["action"] == "cut"
    wx, wy = _disp("upper midWing")
    assert sg["coords"]["x"] == wx and sg["coords"]["y"] == wy


def test_non_bh_holds_when_gate_high():
    beat = build_subtle_beat(_step({"PG": "key", "SG": "upper wing"}), _lineup("PG", "SG"),
                             "PG", is_away_offense=False, rng=FakeRng(choice_idx=0, random_val=1.0))
    sg = beat["pos_actions"]["SG"]
    wx, wy = _disp("upper wing")
    assert sg["action"] == "stationary" and sg["coords"]["x"] == wx and sg["coords"]["y"] == wy


# ---------------------------------------------------------------- shape / UESS

def test_all_offense_present_and_coords_explicit():
    off = _lineup("PG", "SG", "SF", "PF", "C")
    step = _step({"PG": "key", "SG": "upper wing", "SF": "lower wing", "PF": "upper lowPost", "C": "basketSpot"})
    beat = build_subtle_beat(step, off, "PG", is_away_offense=False, rng=FakeRng(choice_idx=0, random_val=1.0))
    assert set(beat["pos_actions"]) == {"PG", "SG", "SF", "PF", "C"}
    assert all("coords" in pa for pa in beat["pos_actions"].values())
    assert beat["pos_actions"]["PG"]["action"] == "handle_ball"  # BH keeps the ball


def test_subtle_movers_use_drift_archetype():
    off = _lineup("PG", "SG")
    beat = build_subtle_beat(_step({"PG": "key", "SG": "upper wing"}), off,
                             "PG", is_away_offense=False, rng=FakeRng(choice_idx=1, random_val=0.0))
    assert beat["pos_actions"]["PG"]["archetype"] == "drift"   # BH dribble
    for pa in beat["pos_actions"].values():
        if pa["action"] == "cut":
            assert pa["archetype"] == "drift"                  # non-BH movers
        if pa["action"] == "stationary":
            assert "archetype" not in pa                       # holders untouched


def test_emitter_archetype_map_respects_explicit_override():
    from BackEnd.engine.skeleton_step_emitter import _build_archetype_map

    class _P:
        def __init__(self, pid):
            self.player_id = pid

    off = {"PG": _P("off_pg"), "SG": _P("off_sg")}
    deff = {"PG": _P("def_pg")}
    actions = {"off_pg": "cut", "off_sg": "cut", "def_pg": "guard_offball"}
    pos_actions = {"PG": {"action": "cut", "archetype": "drift"}, "SG": {"action": "cut"}}
    arch = _build_archetype_map(off, deff, actions, "HCO", pos_actions=pos_actions)
    assert arch["off_pg"] == "drift"        # explicit override wins
    assert arch["off_sg"] == "cruise"       # no override → HCO cut default


def test_returns_none_when_bh_absent_from_step():
    assert build_subtle_beat(_step({"SG": "upper wing"}), _lineup("PG", "SG"),
                             "PG", is_away_offense=False, rng=FakeRng()) is None
