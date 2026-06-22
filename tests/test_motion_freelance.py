"""Phase 5 tests — Dynamic HCO Motion freelance movement-beat emission."""
import math
from BackEnd.engine.motion_freelance import build_freelance_beat, FREELANCE_RELOCATE_RADIUS
from BackEnd.engine.attack_drive_clearance import _spot_display_coords


class _FakePlayer:
    def __init__(self, pid):
        self.player_id = pid


class FakeRng:
    def __init__(self, choice_idx=0, randint_val=3, random_val=0.0):
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


_LOCS = {"PG": "key", "SG": "upper wing", "SF": "lower wing", "PF": "upper lowPost", "C": "basketSpot"}


def test_all_players_move_bh_keeps_ball():
    off = _lineup(*_LOCS)
    beat = build_freelance_beat(_step(_LOCS), off, "PG", off_efficiency=0, team_chemistry=7,
                                is_away_offense=False, rng=FakeRng(random_val=0.0))  # subtle nudges
    assert set(beat["pos_actions"]) == set(_LOCS)
    assert beat["pos_actions"]["PG"]["action"] == "handle_ball"
    assert all(p == "PG" or pa["action"] == "cut" for p, pa in beat["pos_actions"].items())
    assert all("coords" in pa for pa in beat["pos_actions"].values())


def test_relocate_targets_are_within_radius():
    off = _lineup("PG")
    beat = build_freelance_beat(_step({"PG": "key"}), off, "PG", off_efficiency=0, team_chemistry=7,
                                is_away_offense=False, rng=FakeRng(random_val=1.0, choice_idx=0))  # relocate
    key = _spot_display_coords("key", False)
    new = beat["pos_actions"]["PG"]["coords"]
    d = math.hypot(new["x"] - key["x"], new["y"] - key["y"])
    assert 0 < d <= FREELANCE_RELOCATE_RADIUS + 0.1   # moved to a *new* nearby spot


def test_uniqueness_enforced_when_team_is_sharp():
    # off_eff + chem = 30 > 15 → all relocate targets distinct.
    off = _lineup(*_LOCS)
    beat = build_freelance_beat(_step(_LOCS), off, "PG", off_efficiency=10, team_chemistry=20,
                                is_away_offense=False, rng=FakeRng(random_val=1.0, choice_idx=0))
    coords = [(pa["coords"]["x"], pa["coords"]["y"]) for pa in beat["pos_actions"].values()]
    assert len(coords) == len(set(coords))            # no shared spots
    assert beat["_freelance"]["enforce_unique"] is True
    assert beat["_freelance"]["collisions"] == []


def test_collision_offsets_coincident_players_backend():
    from BackEnd.engine.motion_freelance import _resolve_collisions
    # Two players land on the same spot; backend must separate them (FE computes nothing).
    pa = {"PG": {"coords": {"x": 50.0, "y": 25.0}, "action": "handle_ball"},
          "SG": {"coords": {"x": 50.0, "y": 25.0}, "action": "cut"}}
    collisions = _resolve_collisions(pa, enforce_unique=False)
    xs = {pa["PG"]["coords"]["x"], pa["SG"]["coords"]["x"]}
    assert len(xs) == 2                       # now distinct
    assert pa["PG"]["coords"]["x"] != pa["SG"]["coords"]["x"]
    assert abs(pa["PG"]["coords"]["x"] - pa["SG"]["coords"]["x"]) == 4.0   # ±2 each, opposite
    assert ["PG", "SG"] in collisions          # tagged for FE rattle


def test_collision_separated_silently_when_sharp():
    from BackEnd.engine.motion_freelance import _resolve_collisions
    pa = {"PG": {"coords": {"x": 50.0, "y": 25.0}, "action": "handle_ball"},
          "SG": {"coords": {"x": 50.0, "y": 25.0}, "action": "cut"}}
    collisions = _resolve_collisions(pa, enforce_unique=True)
    assert pa["PG"]["coords"]["x"] != pa["SG"]["coords"]["x"]   # still separated (no overlap ever)
    assert collisions == []                    # but no rattle for a sharp team


def test_returns_none_when_bh_absent():
    off = _lineup("PG", "SG")
    assert build_freelance_beat(_step({"SG": "upper wing"}), off, "PG", 0, 7, False, FakeRng()) is None
