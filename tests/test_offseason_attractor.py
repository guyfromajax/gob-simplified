"""Offseason development: Part A (anchor/live sync) and Part B (shape-and-level attractor).

These pin the two halves of the 2026-08 offseason fix, measured through the path production
actually takes — the CPU in-season training (reference base + player-maximizer-custom
amplifier) alternating with develop_rollover — NOT the bare reference the older invariants
use, which never described production.

The absence of the first assertion here cost the project a full validation cycle: develop
wrote only `live`, so week-1 training (which reads `anchor_` and resets `live = anchor`) wiped
every offseason growth on any attribute it did not itself train, and RT masked it.
"""
import contextlib
import logging
import os
import random
import statistics

logging.disable(logging.CRITICAL)

from BackEnd.utils import player_development as dev
from BackEnd.utils import player_generation as gen
from BackEnd.utils.player_generation import position_profile
from BackEnd.utils.position_ratings import POSITION_WEIGHTS, height_fitness, compute_position_ratings
from BackEnd.models.training_execution_v2 import execute_training
from BackEnd.api.franchise_routes import _cpu_reference_allocation, _cpu_reference_top3

POSITIONS = ("PG", "SG", "SF", "PF", "C")
GROWTH = list(dev.GROWTH_ATTRS)
_NULL = open(os.devnull, "w")
_ALLOC = _cpu_reference_allocation()


def _cpu_train_week(fpd, year, weeks=26):
    """Run the ACTUAL CPU in-season path for one season, mutating fpd['attributes']."""
    pl = [{"_id": "x", "attributes": fpd["attributes"], "year": year, "height": fpd["meta"]["height"],
           "meta": fpd["meta"], "position_intent": fpd["position_intent"], "first_name": "A", "last_name": "B"}]
    top3 = _cpu_reference_top3(fpd["position_intent"])
    with contextlib.redirect_stdout(_NULL):
        for wk in range(weeks):
            execute_training(pl, {}, _ALLOC, "player-maximizer-custom",
                             coaching_focus_custom_by_player={"x": top3},
                             skip_pre_training_depreciation=(wk == 0))
    fpd["attributes"] = pl[0]["attributes"]
    fpd["position_ratings"] = compute_position_ratings(
        {"attributes": fpd["attributes"], "height": fpd["meta"]["height"]})


def _fresh(pos, tier, seed):
    rng = random.Random(seed)
    jh = gen.generate_player(pos, "JH", tier, rng)
    return {"player_id": "x", "meta": {"year": "JH", "height": jh["height"], "weight": jh["weight"]},
            "attributes": dict(jh["attributes"]), "position_ratings": dict(jh["position_ratings"]),
            "entry_tier": tier, "position_intent": pos}, rng


def test_partA_writes_both_and_full_cycle_preserves_growth():
    """PART A. develop must (1) write anchor_ AND live equal, and (2) have that growth
    SURVIVE a subsequent week-1 in-season training (which reads anchor_ and resets
    live=anchor). Pre-fix, week-1 reset live to a stale anchor and the offseason growth
    vanished — the defect that had no test."""
    fpd, rng = _fresh("C", "Average", 3)
    # develop through three rungs so SC is well above its JH value
    for y in ("freshman", "sophomore", "junior"):
        out = dev.develop_rollover(fpd, y, rng, season_allocation=None)
        for k in ("attributes", "position_ratings", "development"):
            fpd[k] = out[k]
        fpd["meta"]["height"] = out["height"]; fpd["meta"]["weight"] = out["weight"]
        fpd["entry_tier"] = out["entry_tier"]; fpd["meta"]["year"] = y
    # (1) develop wrote both fields, synced
    for a in GROWTH:
        assert fpd["attributes"][f"anchor_{a}"] == fpd["attributes"][a], f"{a}: anchor≠live after develop"
    grown = fpd["attributes"]["anchor_SC"]
    assert grown > 40, f"attractor should develop a C's SC well above JH ({grown})"
    # (2) one week-1 CPU training must preserve it (not reset to a stale pre-develop value)
    _cpu_train_week(fpd, "junior", weeks=1)
    after = fpd["attributes"]["anchor_SC"]
    assert after >= grown - 5, (
        f"week-1 training wiped offseason growth: anchor_SC {grown} → {after}. "
        f"develop must write anchor_ (Part A), and in-season must build on it.")


def test_cpu_path_preserves_shape():
    """PART B, the invariant replacing 'reference holds flat': a reference-coached player
    developed through the ACTUAL CPU path lands with his tier/year/position PROFILE
    preserved — non-signature attributes are not starved. This is what the old bare-reference
    invariants could not see, and what the desync+ratchet violated (C scoring 44→26).

    Averaged over seeds: a single career carries large peak/HT variance, so this is a
    DISTRIBUTIONAL property (the league's mean developed shape), not a per-career one."""
    N = 12
    for pos in POSITIONS:
        finals = []
        for s in range(N):
            fpd, rng = _fresh(pos, "Average", 100 + s)
            for y in ("freshman", "sophomore", "junior", "senior"):
                out = dev.develop_rollover(fpd, y, rng, season_allocation=None)
                for k in ("attributes", "position_ratings", "development"):
                    fpd[k] = out[k]
                fpd["meta"]["height"] = out["height"]; fpd["meta"]["weight"] = out["weight"]
                fpd["entry_tier"] = out["entry_tier"]; fpd["meta"]["year"] = y
                if y != "senior":
                    _cpu_train_week(fpd, y)
            finals.append(dict(fpd["attributes"], **{"_rt": max(fpd["position_ratings"].values()),
                                                     "_h": fpd["meta"]["height"]}))
        mean_attr = {a: statistics.mean(f[f"anchor_{a}"] for f in finals) for a in GROWTH}
        prof = position_profile(pos); w = POSITION_WEIGHTS[pos]
        fit = height_fitness(pos, statistics.mean(f["_h"] for f in finals)) or 1.0
        rt = statistics.mean(f["_rt"] for f in finals)
        denom = sum(w.get(a, 0.0) * prof.get(a, 0.0) for a in GROWTH) or 1.0
        k = (rt / fit) / denom
        # no on-position attribute is starved below 70% of its profile target. The attractor
        # is partial by design (α<1), so it lands below 100% — but the collapse drove SC to
        # ~45% of target, which this catches while passing healthy development (~90%).
        for a in GROWTH:
            if w.get(a, 0.0) >= 0.10:
                target = prof[a] * k
                assert mean_attr[a] >= 0.70 * target, (
                    f"{pos}/{a}: mean developed {mean_attr[a]:.0f} starved vs profile target "
                    f"{target:.0f} (<70%). Non-signature attributes must not collapse on turnover.")
        if pos == "C":                                  # the attribute that collapsed to 26 live
            assert mean_attr["SC"] > 48, \
                f"C mean scoring {mean_attr['SC']:.0f} — the shooting collapse regressed."
