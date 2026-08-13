"""Pass-2-step-2 wiring gates: the growth profile survives a rollover, nobody
develops twice, and the offseason event tracks the ladder. Pure (no DB)."""
import inspect
import random

import pytest

from BackEnd.utils import player_development as dev
from BackEnd.utils.player_generation import JH_ANCHOR_BY_TIER


def _fpd_from_player(pl: dict) -> dict:
    """Shape an in-memory career player as an FPD document (what finish_season
    forward-copies), carrying the development pointer fields."""
    return {
        "player_id": "p1",
        "meta": {"first_name": "Test", "last_name": "Player",
                 "height": pl["height"], "weight": pl["weight"], "year": pl["class_year"]},
        "attributes": dict(pl["attributes"]),
        "position_ratings": dict(pl["position_ratings"]),
        "development": pl["development"],
        "entry_tier": pl["tier"],
        "position_intent": pl["position"],
    }


def test_development_survives_rollover():
    """NON-NEGOTIABLE: a player's development profile is intact after a rollover
    and does not re-roll — same peaks, same timing, same ch_seed."""
    rng = random.Random(1)
    pl = dev.simulate_career("SF", "Good", 72, rng)
    # Snapshot his frozen profile, then simulate the FR->SO rollover step.
    doc = _fpd_from_player(pl)
    doc["meta"]["year"] = "sophomore"
    before = dict(doc["development"])
    result = dev.develop_rollover(doc, "sophomore", random.Random(2))
    assert result["development"]["peak_count"] == before["peak_count"]
    assert result["development"]["peak_rungs"] == before["peak_rungs"]
    assert result["development"]["family_timing"] == before["family_timing"]
    assert result["development"]["ch_seed"] == before["ch_seed"]
    assert result["backfilled"] is False  # already had a profile → not re-rolled


def test_lazy_backfill_rolls_once_on_remaining_rungs():
    """A legacy doc with NO development gets one rolled + returned to persist; peaks
    land only on remaining rungs; a second pass with the persisted profile does not
    re-roll (career-stable)."""
    doc = {
        "player_id": "legacy", "meta": {"height": 79, "weight": 210, "year": "junior"},
        "attributes": {"anchor_CH": 90, "CH": 90, "SC": 50, "SH": 50, "ID": 50, "OD": 50,
                       "PS": 50, "BH": 50, "RB": 50, "ST": 50, "AG": 50, "IQ": 50, "FT": 50, "ND": 50},
        "position_ratings": {"PG": 30, "SG": 35, "SF": 55, "PF": 40, "C": 30},
        # no development / entry_tier / position_intent
    }
    r1 = dev.develop_rollover(doc, "junior", random.Random(5))
    assert r1["backfilled"] is True
    assert r1["development"] is not None
    # rolling onto JR → remaining rungs are JR, SR; no peak may sit on FR/SO.
    assert all(rr in ("JR", "SR") for rr in r1["development"]["peak_rungs"])
    # persist it, roll again → uses stored profile, no re-roll.
    doc["development"] = r1["development"]
    doc["entry_tier"] = r1["entry_tier"]
    doc["position_intent"] = r1["position_intent"]
    r2 = dev.develop_rollover(doc, "junior", random.Random(6))
    assert r2["backfilled"] is False
    assert r2["development"]["peak_rungs"] == r1["development"]["peak_rungs"]


def test_offseason_adds_reduced_increment_not_the_ladder():
    """FREE-WILL: the offseason no longer rescales onto the ladder (it used to be the sole
    grower, landing a 0-peak SR at ~1.70× the anchor). It now ADDS a REDUCED increment per
    rung on top of the player's current RT — a small positive step each rung — so training
    can carry the career. A 0-peak player driven through develop_one_offseason ends FAR below
    the old ladder (a regression to the absolute rescale reappears as SR ≈ 1.70× anchor)."""
    rng = random.Random(0)
    pl = dev.init_career("SG", "Average", 3, rng)[0]  # low CH → 0-1 peaks
    profile = dict(pl["development"]); profile["peak_rungs"] = []  # pin 0-peak
    anchor = JH_ANCHOR_BY_TIER["Average"]
    player = {"attributes": dict(pl["attributes"]), "height": pl["height"], "weight": pl["weight"],
              "position": "SG", "training_position": "SG", "jh_anchor": anchor,
              "position_ratings": dict(pl["position_ratings"])}
    start = player["position_ratings"]["SG"]
    prev = start
    for rung in dev.RUNG_TRANSITIONS:
        dev.develop_one_offseason(player, rung, profile, random.Random(9))
        now = player["position_ratings"]["SG"]
        # non-decreasing per rung (the reduced increment can be sub-1-RT and round to 0)
        assert now >= prev, f"{rung}: offseason must not REMOVE RT (was {prev:.1f}, now {now:.1f})."
        prev = now
    assert player["position_ratings"]["SG"] > start, (
        "offseason must net-ADD across the career (additive increment).")
    assert player["position_ratings"]["SG"] < anchor * 1.40, (
        f"0-peak offseason-only SR {player['position_ratings']['SG']:.1f} reached the old ladder "
        f"(~{anchor * 1.70:.0f}) — the absolute-target rescale has regressed. Free-will adds a reduced increment.")


def test_camp_growth_calls_removed_from_training_path():
    """No double-develop: the offseason event owns the CH bonus, year bonus and
    FR/SO HT/WT, so the training-camp path must no longer call any of them."""
    from BackEnd.models import training_execution_v2 as tev
    src = inspect.getsource(tev.apply_training_points)
    for gone in ("_apply_training_camp_bonus(",
                 "_apply_training_camp_height_weight_bonuses("):
        assert gone not in src, f"camp still calls {gone} — players would develop twice"


def test_weekly_decay_reduced():
    """In-season decay came down substantially (§7.2) — no year worse than -2/attr."""
    from BackEnd.models.training_execution_v2 import PRE_TRAINING_DECAY_BY_YEAR
    for year, (lo, hi) in PRE_TRAINING_DECAY_BY_YEAR.items():
        assert lo >= -2, year
        assert hi <= 0, year


def _ranked(pos):
    w = dev.POSITION_WEIGHTS[pos]
    return sorted((a for a in w if w[a] > 0), key=lambda a: -w[a])


def test_reference_scores_one_and_points_band_bounds():
    """Points-based saturating-coverage metric. The frozen mediocre reference (~what
    CPU trains) scores exactly 1.0 → f 1.0 at every position, so a reference-coached
    player lands on the validated ladder. Focus and broad coverage beat it; all-in,
    off-position, and uniform-across-all-12 fall below; headroom is equal across
    positions. Allocations are POINTS/week (0-5 per attribute), not shares."""
    smax, budget = dev.COACHING_SLIDER_MAX, dev.COACHING_STANDARD_BUDGET
    for pos in ("PG", "SG", "SF", "PF", "C"):
        assert abs(dev.season_coaching_quality(dev.reference_allocation(pos), pos) - 1.0) < 1e-9, pos
        assert dev.coaching_f(1.0) == 1.0, pos
        r = _ranked(pos)
        # all-in: the single top attribute maxed, nothing else → below reference, floor.
        allin = dev.season_coaching_quality({r[0]: smax}, pos)
        assert allin < 1.0, pos
        assert dev.coaching_f(allin) == dev.COACHING_F_MIN, pos
        # focus is VIABLE now (not floored): 3 relevant attrs maxed + baseline → above 1.0.
        focus3 = {a: (smax if a in r[:3] else 1.0) for a in r}
        assert dev.season_coaching_quality(focus3, pos) > 1.0, pos
        # a 2-point smaller budget saturates fewer attributes → strictly lower quality
        # (the customization tax prices itself; no special-casing).
        ref = dev.reference_allocation(pos)
        cut = dict(ref); cut[r[-1]] = max(0.0, cut[r[-1]] - 2.0)
        assert dev.season_coaching_quality(cut, pos) < 1.0, pos
    # off-position (points only on zero-weight attributes) → 0 coverage → floor.
    off = {a: dev.COACHING_SLIDER_MAX for a in ("EM",)}  # not in any weight vector
    assert dev.coaching_f(dev.season_coaching_quality(off, "SG")) == dev.COACHING_F_MIN
    # HEADROOM EQUALIZED: the budget optimum reaches ~the band max at every position,
    # so coaching matters equally at SF (flattest) and SG (most concentrated).
    for pos in ("PG", "SG", "SF", "PF", "C"):
        r = _ranked(pos)
        opt = {a: smax for a in r[:4]} | {a: 1.0 for a in r[4:]}
        assert dev.coaching_f(dev.season_coaching_quality(opt, pos)) >= 1.15, pos


def test_season_allocation_scored_against_training_position():
    """§9.2: a player converted toward a new position (training_position != natural
    position_intent) is scored against training_position, so executing the designed
    conversion is not double-charged as low coaching quality. training_position
    defaults to position_intent and is forward-copied."""
    base = {"player_id": "conv", "meta": {"height": 79, "weight": 210, "year": "sophomore"},
            "attributes": {f"anchor_{a}": 45 for a in dev.GROWTH_ATTRS}
                          | {a: 45 for a in dev.GROWTH_ATTRS} | {"CH": 55, "anchor_CH": 55},
            "position_ratings": {"PG": 40, "SG": 35, "SF": 50, "PF": 45, "C": 30},
            "position_intent": "SF", "training_position": "PG", "entry_tier": "Average",
            "development": {"peak_count": 0, "peak_rungs": [], "ch_seed": 55,
                            "family_timing": {"physical": "standard", "skill": "standard", "mental": "standard"},
                            "ht_total": 3}}
    # Train the PG reference exactly: scored against training_position (PG) this is
    # 1.0. Scored against position_intent (SF) it would NOT be 1.0 → the penalty the
    # weight tables already price. n was 0, so cumulative avg == this season's score.
    import copy
    pg_ref = dev.reference_allocation("PG")
    out = dev.develop_rollover(copy.deepcopy(base), "sophomore", random.Random(1), season_allocation=pg_ref)
    assert out["training_position"] == "PG"  # forward-copied
    assert abs(out["coaching_quality"]["avg"] - 1.0) < 1e-9
    assert out["coaching_quality"]["n"] == 1
    # sanity: the same allocation scored against SF (the natural fit) is NOT 1.0,
    # which is exactly the double-charge we avoid by scoring against training_position.
    assert abs(dev.season_coaching_quality(pg_ref, "SF") - 1.0) > 0.05
    # training_position defaults to position_intent when the field is absent.
    no_tp = copy.deepcopy(base); no_tp.pop("training_position")
    out2 = dev.develop_rollover(no_tp, "sophomore", random.Random(1), season_allocation=None)
    assert out2["training_position"] == "SF"


def test_coaching_f_retired_no_longer_modulates_offseason():
    """FREE-WILL (decision 0.5): coaching_f is RETIRED — the additive offseason no longer
    scales by a coaching-quality factor (in-season training IS the coaching lever now). A
    doc's coaching_quality history must therefore NOT change its offseason outcome."""
    base = {"player_id": "q", "meta": {"height": 76, "weight": 190, "year": "sophomore"},
            "attributes": {f"anchor_{a}": 40 for a in dev.GROWTH_ATTRS}
                          | {a: 40 for a in dev.GROWTH_ATTRS} | {"CH": 50, "anchor_CH": 50},
            "position_ratings": {"PG": 30, "SG": 44, "SF": 35, "PF": 30, "C": 28},
            "position_intent": "SG", "entry_tier": "Average",
            "development": {"peak_count": 0, "peak_rungs": [], "ch_seed": 50,
                            "family_timing": {"physical": "standard", "skill": "standard", "mental": "standard"},
                            "ht_total": 3}}
    import copy
    hi = dev.develop_rollover(copy.deepcopy(base) | {"coaching_quality": {"avg": 1.20, "n": 4}}, "sophomore", random.Random(1))
    lo = dev.develop_rollover(copy.deepcopy(base) | {"coaching_quality": {"avg": 0.80, "n": 4}}, "sophomore", random.Random(1))
    none = dev.develop_rollover(copy.deepcopy(base), "sophomore", random.Random(1))  # no history
    assert hi["position_ratings"]["SG"] == none["position_ratings"]["SG"] == lo["position_ratings"]["SG"], (
        "coaching_f is retired under free-will — the offseason outcome must not depend on "
        "coaching_quality history.")
