"""Universal Shoot Decision (brief: Proposed: Universal Shoot Decision) — unit tests for
`should_shoot` and its helpers: weighted attack/outside pick with team bias, clock/tempo-scaled
threshold, read tiers, dish selection, openness bonus, and the reception (no-dish) mode."""
from BackEnd.engine import motion_step_decision as D
from BackEnd.engine.motion_step_decision import (
    should_shoot, _weighted_attack_or_outside, _shoot_threshold, _shoot_read_tier,
)

_ATTR = ["SC", "ST", "AG", "SH", "ID", "OD", "IQ", "CH", "BH"]


class _P:
    def __init__(self, pid, **ov):
        self.player_id = pid
        self.attributes = {k: 50 for k in _ATTR}
        self.attributes.update(ov)


class _Team:
    def __init__(self, discipline=0, attack=2, outside=2):
        self.team_attributes = {"discipline": discipline, "team_chemistry": 7}
        self.strategy_settings = {"attack": attack, "outside": outside}


class Rng:
    def __init__(self, randints=None, random_val=0.0):
        self.q = list(randints or [])
        self.random_val = random_val

    def randint(self, a, b):
        v = self.q.pop(0) if self.q else 3
        return min(max(v, a), b)

    def random(self):
        return self.random_val


# ---------------------------------------------------------------- weighted attack/outside

def test_weighted_pick_team_emphasis_shifts_the_boundary():
    bal = _P("p")  # AG=SC=SH=50 → base attack 50, outside 50
    # Balanced settings (2/2): attack 70 / outside 70 → roll 60 lands on attack (<=70).
    assert _weighted_attack_or_outside(bal, _Team(attack=2, outside=2), Rng([60])) == "attack"
    # Outside-heavy (attack 0 / outside 4): attack 50 / outside 90 → same roll 60 now picks outside.
    assert _weighted_attack_or_outside(bal, _Team(attack=0, outside=4), Rng([60])) == "outside"


# ---------------------------------------------------------------- threshold scaling

def test_threshold_lowers_with_clock_and_tempo():
    base = _shoot_threshold(30, "normal")        # full clock, normal → BASE
    drained = _shoot_threshold(0, "normal")       # empty clock → ~0
    fast = _shoot_threshold(30, "fast")           # fast lowers the bar
    assert base == D.SHOOT_THRESHOLD_BASE
    assert drained < base and abs(drained) < 1e-9
    assert fast == base - D.SHOOT_TEMPO_ADJ["fast"]


# ---------------------------------------------------------------- read tier

def test_read_tier_bands():
    smart = _P("s", IQ=100, CH=100)  # read_raw 100
    assert _shoot_read_tier(smart, _Team(), Rng([3])) == "right"   # 300 > 200
    assert _shoot_read_tier(smart, _Team(), Rng([2])) == "safe"    # 200 (not >200) > 125
    assert _shoot_read_tier(smart, _Team(), Rng([1])) == "random"  # 100 <= 125


# ---------------------------------------------------------------- should_shoot (inside loc → no pick roll)

def _inside_call(scores, bh=None, openness=0.0, allow_dish=True, randints=None, random_val=0.0,
                 lineup=None, locations=None):
    bh = bh or _P("bh", IQ=100, CH=100)
    lineup = lineup or {"PG": bh}
    locations = locations or {"PG": "basketSpot"}
    return should_shoot("PG", lineup, locations, scores, _Team(),
                        shot_clock=30, tempo_call="normal", rng=Rng(randints, random_val),
                        openness=openness, allow_dish=allow_dish)


def test_right_tier_optimal_self_shoots():
    dec = _inside_call({"bh": {"inside": 40.0}}, randints=[3])  # quality 40 >= 30, tier right
    assert dec and dec["action"] == D.SHOOT and dec["shooter_pos"] == "PG"
    assert dec["via_pass"] is False and dec["hot_read"] is True  # 40 > READ_THRESHOLD → mismatch label


def test_right_tier_not_optimal_progresses():
    assert _inside_call({"bh": {"inside": 10.0}}, randints=[3]) is None  # quality 10 < 30


def test_safe_tier_always_progresses_even_when_optimal():
    assert _inside_call({"bh": {"inside": 40.0}}, randints=[2]) is None  # tier safe


def test_random_tier_shoots_or_progresses_on_coin_flip():
    assert _inside_call({"bh": {"inside": 40.0}}, randints=[1], random_val=0.0) is not None   # shoot
    assert _inside_call({"bh": {"inside": 40.0}}, randints=[1], random_val=0.9) is None        # progress


def test_openness_lifts_a_sub_threshold_look_over_the_bar():
    assert _inside_call({"bh": {"inside": 10.0}}, openness=0.0, randints=[3]) is None      # 10 < 30
    dec = _inside_call({"bh": {"inside": 10.0}}, openness=25.0, randints=[3])               # 35 >= 30
    assert dec and dec["action"] == D.SHOOT


def test_dish_to_better_positioned_teammate():
    bh = _P("bh", IQ=100, CH=100)
    sg = _P("sg")
    scores = {"bh": {"inside": 0.0}, "sg": {"inside": 50.0}}      # BH no look, teammate optimal
    dec = should_shoot("PG", {"PG": bh, "SG": sg}, {"PG": "basketSpot", "SG": "midLane"},
                       scores, _Team(), shot_clock=30, tempo_call="normal", rng=Rng([3]))
    assert dec and dec["shooter_pos"] == "SG" and dec["via_pass"] is True


def test_reception_mode_never_dishes():
    bh = _P("bh", IQ=100, CH=100)
    sg = _P("sg")
    scores = {"bh": {"inside": 0.0}, "sg": {"inside": 50.0}}
    # allow_dish=False: BH's own look is not optimal → progress, never dishes to SG.
    dec = should_shoot("PG", {"PG": bh, "SG": sg}, {"PG": "basketSpot", "SG": "midLane"},
                       scores, _Team(), shot_clock=30, tempo_call="normal", rng=Rng([3]),
                       allow_dish=False)
    assert dec is None


# ---------------------------------------------------------------- blocked dish targets (§4 gate)

def test_blocked_dish_target_is_excluded_from_hot_read():
    # PG (BH) has no look; SG has an optimal inside mismatch. High-read PG → 'right' tier.
    pg = _P("pg", IQ=90, CH=90)
    sg = _P("sg")
    off = {"PG": pg, "SG": sg}
    locations = {"PG": "basketSpot", "SG": "basketSpot"}  # inside → no _weighted rng draw
    reads = {"sg": {"inside": 100}, "pg": {"inside": 0}}    # SG optimal+mismatch; PG nothing
    team = _Team()
    # Lane clear → dishes to SG.
    d = should_shoot("PG", off, locations, reads, team, 30, "normal", Rng([6]), allow_dish=True)
    assert d and d["shooter_pos"] == "SG" and d["via_pass"] is True
    # SG's lane covered → excluded → PG not optimal → progress (None).
    d2 = should_shoot("PG", off, locations, reads, team, 30, "normal", Rng([6]),
                      allow_dish=True, blocked_dish_targets={"SG"})
    assert d2 is None
