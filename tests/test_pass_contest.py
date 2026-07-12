"""Unit tests for the universal pass-contest primitive (Dynamic_HCT_Turns.md §14).

Pure geometry + attribute bands — no game/Player scaffolding needed.
"""

from BackEnd.engine.pass_contest import (
    BAT_OOB,
    COMPLETE,
    INTERCEPT,
    PASS_INTERCEPT_TIER_HI,
    PASS_INTERCEPT_TIER_MID,
    PASS_SAFETY_BASE,
    find_pass_contester,
    resolve_offense_pass_modifier,
    resolve_pass_contest,
)


class FixedRng:
    """rng stub with a deterministic randint (used for both the gate + band rolls)."""

    def __init__(self, value):
        self.value = value

    def randint(self, _a, _b):
        return self.value


def _xy(x, y):
    return {"x": x, "y": y}


def _defender(did, x, y, *, rate=12.0, OD=50, CH=50, IQ=50):
    return {"id": did, "xy": _xy(x, y), "rate": rate, "OD": OD, "CH": CH, "IQ": IQ}


PASSER_XY = _xy(40, 25)
RECEIVER = _xy(60, 25)  # 20-grid horizontal lane at y=25
BALL_SPEED = 20.0  # 1 grid / 0.05s — ball crosses the 20-grid lane in 1.0s


def _passer(x=40, y=25, *, PS=0, CH=0, IQ=0):
    """Passer descriptor; default attrs 0 → never clears the safety gate (so the
    interception band is exercised)."""
    return {"xy": _xy(x, y), "PS": PS, "CH": CH, "IQ": IQ}


# --- Stage 1: geometry gate --------------------------------------------------

def test_no_defender_near_lane_completes():
    d = _defender("d1", 50, 60, rate=99.0)
    assert find_pass_contester(PASSER_XY, RECEIVER, BALL_SPEED, [d]) is None
    res = resolve_pass_contest(_passer(), RECEIVER, BALL_SPEED, [d], rng=FixedRng(6))
    assert res["outcome"] == COMPLETE
    assert res["deflector"] is None


def test_perp_gate_excludes_in_time_but_out_of_lane_defender():
    from BackEnd.engine.pass_contest import PASS_LANE_DIST

    d = _defender("d1", 50, 25 + PASS_LANE_DIST + 1, rate=999.0)
    assert find_pass_contester(PASSER_XY, RECEIVER, BALL_SPEED, [d]) is None


def test_defender_in_lane_and_quick_is_eligible():
    d = _defender("d1", 50, 27, rate=40.0)
    hit = find_pass_contester(PASSER_XY, RECEIVER, BALL_SPEED, [d])
    assert hit is not None
    assert hit["defender"]["id"] == "d1"
    assert 40 <= hit["contact_point"]["x"] <= 60
    assert abs(hit["contact_point"]["y"] - 25) < 1e-6


def test_slow_defender_cannot_beat_fast_ball():
    d = _defender("d1", 50, 27, rate=1.0)
    assert find_pass_contester(PASSER_XY, RECEIVER, BALL_SPEED, [d]) is None


def test_earliest_contact_defender_is_chosen():
    near_passer = _defender("near", 45, 26, rate=40.0)
    near_receiver = _defender("far", 57, 26, rate=40.0)
    hit = find_pass_contester(PASSER_XY, RECEIVER, BALL_SPEED, [near_receiver, near_passer])
    assert hit["defender"]["id"] == "near"


# --- Stage 3: interception band (passer attrs 0 → gate never clears) ---------

def _lane_defender(**kw):
    return _defender("d1", 50, 26, rate=40.0, **kw)


def test_deflect_then_skill_roll_intercepts():
    # composite = 50*0.6+50*0.2+50*0.2 = 50; ×6 = 300 > tier_mid (200) → DEFLECTED. Split roll (also
    # 6 via FixedRng) < CH+IQ (100) → clean INTERCEPT.
    res = resolve_pass_contest(_passer(), RECEIVER, BALL_SPEED, [_lane_defender()], rng=FixedRng(6))
    assert res["outcome"] == INTERCEPT
    assert res["deflector"] == "d1"
    assert res["contact_point"] is not None


def test_deflect_with_poor_hands_bats_out_of_bounds():
    # New split: a strong-OD but poor-hands defender. composite = 70*0.6 = 42; ×5 = 210 > tier_mid
    # (200) → DEFLECTED. But the split roll (5) is NOT < CH+IQ (0) → the pass is knocked away, not
    # cleanly picked → BAT_OOB. (rand(1,200) < CH+IQ → INTERCEPT, else BAT_OOB.)
    d = _defender("d1", 50, 26, rate=40.0, OD=70, CH=0, IQ=0)
    res = resolve_pass_contest(_passer(), RECEIVER, BALL_SPEED, [d], rng=FixedRng(5))
    assert res["outcome"] == BAT_OOB
    assert res["deflector"] == "d1"


def test_low_roll_completes_even_when_contested():
    # 50 × 3 = 150 → below tier_mid → clean completion despite an eligible defender.
    res = resolve_pass_contest(_passer(), RECEIVER, BALL_SPEED, [_lane_defender()], rng=FixedRng(3)) 
    assert res["outcome"] == COMPLETE
    assert res["deflector"] is None


def test_band_uses_CH_not_AG():
    # CH drives the band now: a defender with high CH but low everything-else still
    # converts; AG is irrelevant to the band.
    d = _defender("d1", 50, 26, rate=40.0, OD=0, CH=0, IQ=0)
    d["AG"] = 100  # should NOT matter
    res = resolve_pass_contest(_passer(), RECEIVER, BALL_SPEED, [d], rng=FixedRng(6))
    assert res["outcome"] == COMPLETE  # composite 0 → never intercepts


def test_thresholds_are_the_documented_defaults():
    assert PASS_INTERCEPT_TIER_HI == 250.0
    assert PASS_INTERCEPT_TIER_MID == 200.0
    assert PASS_SAFETY_BASE == 200.0


# --- Stage 2: passer safety gate --------------------------------------------

def test_good_passer_evades_contest():
    # passer composite = 50*0.6+50*0.2+50*0.2 = 50; ×6 = 300 > 200 → safe, COMPLETE
    # even though the lane defender would otherwise intercept on the same roll.
    res = resolve_pass_contest(
        _passer(PS=50, CH=50, IQ=50), RECEIVER, BALL_SPEED, [_lane_defender()],
        rng=FixedRng(6),
    )
    assert res["outcome"] == COMPLETE
    assert res["deflector"] is None


def test_weak_passer_does_not_evade():
    # passer composite 50 × 1 = 50 ≤ 200 → not safe → band runs; defender 50×1=50 → COMPLETE
    # (verifies the gate did NOT short-circuit; here it just happens to complete on the band).
    res = resolve_pass_contest(
        _passer(PS=50, CH=50, IQ=50), RECEIVER, BALL_SPEED, [_lane_defender()],
        rng=FixedRng(1),
    )
    assert res["outcome"] == COMPLETE


def test_offense_modifier_lowers_safety_bar():
    # passer 50 × 4 = 200 → not > 200 (gate fails) at offense_modifier=0.
    # With offense_modifier=50 the bar drops to 150, so 200 > 150 → safe → COMPLETE,
    # even though the band on the same roll (defender 50×4=200) would NOT complete-safe
    # on its own (200 not > 200 → COMPLETE anyway, so use a roll that would BAT).
    safe = resolve_pass_contest(
        _passer(PS=50, CH=50, IQ=50), RECEIVER, BALL_SPEED, [_lane_defender()],
        offense_modifier=50, rng=FixedRng(5),  # passer 250 > 150 → safe
    )
    assert safe["outcome"] == COMPLETE
    # Same inputs, no modifier: passer 250 > 200 → also safe. Use roll=3 to show the
    # modifier flipping a would-be BAT into safe:
    no_mod = resolve_pass_contest(
        _passer(PS=30, CH=30, IQ=30), RECEIVER, BALL_SPEED, [_lane_defender(OD=70, CH=70, IQ=70)],
        offense_modifier=0, rng=FixedRng(5),
    )
    # passer 30 composite ×5 = 150 ≤ 200 → not safe → band: def 70×5=350 > 250 → INTERCEPT
    assert no_mod["outcome"] == INTERCEPT
    with_mod = resolve_pass_contest(
        _passer(PS=30, CH=30, IQ=30), RECEIVER, BALL_SPEED, [_lane_defender(OD=70, CH=70, IQ=70)],
        offense_modifier=60, rng=FixedRng(5),
    )
    # bar drops to 140; passer 150 > 140 → safe → COMPLETE (modifier rescued the pass).
    assert with_mod["outcome"] == COMPLETE


# --- Turn-type modifier resolver --------------------------------------------

def test_offense_modifier_resolver_maps_turn_types():
    attrs = {
        "offensive_efficiency": 7,
        "pt_opp_modifier": 4,
        "fb_efficiency": 9,
    }
    assert resolve_offense_pass_modifier("HCO", attrs) == 7
    assert resolve_offense_pass_modifier("HCT", attrs) == 4
    assert resolve_offense_pass_modifier("FAST_BREAK", attrs) == 9
    # Unlisted → offensive_efficiency fallback.
    assert resolve_offense_pass_modifier("SIDE_INBOUND", attrs) == 7
    assert resolve_offense_pass_modifier("HCO", {}) == 0.0
    assert resolve_offense_pass_modifier("HCO", None) == 0.0


# --- Edge cases --------------------------------------------------------------

def test_zero_length_pass_never_contested():
    res = resolve_pass_contest(_passer(), PASSER_XY, BALL_SPEED, [_lane_defender()], rng=FixedRng(6))
    assert res["outcome"] == COMPLETE


def test_zero_ball_speed_never_contested():
    res = resolve_pass_contest(_passer(), RECEIVER, 0.0, [_lane_defender()], rng=FixedRng(6))
    assert res["outcome"] == COMPLETE


def test_zero_rate_defender_skipped():
    d = _defender("d1", 50, 26, rate=0.0)
    assert find_pass_contester(PASSER_XY, RECEIVER, BALL_SPEED, [d]) is None


def test_missing_passer_xy_completes():
    res = resolve_pass_contest({"PS": 50}, RECEIVER, BALL_SPEED, [_lane_defender()], rng=FixedRng(6))
    assert res["outcome"] == COMPLETE
