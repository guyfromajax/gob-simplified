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
from BackEnd.utils.position_ratings import compute_position_ratings
from BackEnd.models.training_execution_v2 import execute_training
from BackEnd.api.franchise_routes import _cpu_reference_allocation, _cpu_reference_top3

POSITIONS = ("PG", "SG", "SF", "PF", "C")
GROWTH = list(dev.GROWTH_ATTRS)
_NULL = open(os.devnull, "w")


def _cpu_train_week(fpd, year, weeks=26):
    """Run the ACTUAL CPU in-season path for one season, mutating fpd['attributes']."""
    from BackEnd.constants.training_shape import CAMP_GAIN_SCALE, is_camp_week
    pl = [{"_id": "x", "attributes": fpd["attributes"], "year": year, "height": fpd["meta"]["height"],
           "meta": fpd["meta"], "position_intent": fpd["position_intent"], "first_name": "A", "last_name": "B"}]
    top3 = _cpu_reference_top3(fpd["position_intent"])
    alloc = _cpu_reference_allocation(fpd["position_intent"])
    with contextlib.redirect_stdout(_NULL):
        for wk in range(1, weeks + 1):
            camp = is_camp_week(wk)
            execute_training(
                pl, {}, alloc, "player-maximizer-custom",
                coaching_focus_custom_by_player={"x": top3},
                skip_pre_training_depreciation=camp,
                gain_scale=CAMP_GAIN_SCALE if camp else None,
            )
    fpd["attributes"] = pl[0]["attributes"]
    fpd["position_ratings"] = compute_position_ratings(
        {"attributes": fpd["attributes"], "height": fpd["meta"]["height"]})


def _fresh(pos, tier, seed):
    rng = random.Random(seed)
    jh = gen.generate_player(pos, "JH", tier, rng)
    # Pin potential_factor to 1.0 (reference ceiling): a test asserting the developed SHAPE
    # must not depend on what hash(player_id) happens to yield — with the fixed id "x" that
    # resolved to 0.90, which silently scaled every developed attribute down ~10%.
    return {"player_id": "x", "meta": {"year": "JH", "height": jh["height"], "weight": jh["weight"]},
            "attributes": dict(jh["attributes"]), "position_ratings": dict(jh["position_ratings"]),
            "entry_tier": tier, "position_intent": pos, "potential_factor": 1.0}, rng


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
    assert grown > 40, f"level-only offseason should develop a C's SC well above JH ({grown})"
    # (2) one week-1 CPU training must preserve it (not reset to a stale pre-develop value)
    _cpu_train_week(fpd, "junior", weeks=1)
    after = fpd["attributes"]["anchor_SC"]
    assert after >= grown - 5, (
        f"week-1 training wiped offseason growth: anchor_SC {grown} → {after}. "
        f"develop must write anchor_ (Part A), and in-season must build on it.")


def test_offseason_alone_is_a_reduced_additive_remainder():
    """FREE-WILL LEVEL invariant (2026-08, predestination → free will). The offseason no
    longer rescales a player onto an absolute ladder (which used to land a developed senior
    at 2.0× his JH anchor by construction). It now ADDS a REDUCED increment, so career growth
    is training-driven. A career walked through the OFFSEASON ONLY (`simulate_career` does no
    in-season training) therefore lands only MODESTLY above the JH anchor (~1.2-1.5×), not the
    old 2.0× ladder. A regression to the absolute-target rescale reappears as SR ≈ 2× the anchor."""
    from BackEnd.utils.player_generation import JH_ANCHOR_BY_TIER
    for tier in ("Poor", "Average", "Elite"):
        jh_anchor = JH_ANCHOR_BY_TIER[tier]
        rng = random.Random(4242)
        srs = []
        for _ in range(2000):
            ch = rng.randint(1, 100)
            pos = POSITIONS[rng.randrange(len(POSITIONS))]
            pl = dev.simulate_career(pos, tier, ch, rng)
            srs.append(pl["snapshots"]["SR"][pos])
        ratio = statistics.median(srs) / jh_anchor
        assert 1.15 < ratio < 1.6, (
            f"{tier}: offseason-only SR median {statistics.median(srs):.1f} = {ratio:.2f}× JH "
            f"anchor {jh_anchor} — expected a reduced additive remainder (~1.2-1.5×), not the "
            f"old 2.0× ladder. Has the absolute-target rescale regressed?")


def test_cpu_path_preserves_shape():
    """PART B (framework §10.4). Without the α-attractor, the CPU path must still
    let coaching move shape — reference top-3 attrs finish above neglected attrs.

    Profile-alignment (≥70% of position_profile) was the attractor's job and is
    deliberately retired; floors replace its anti-starvation half (see
    test_decay_clamps_to_weight_scaled_floor).
    """
    random.seed(20260804)
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
            finals.append(dict(fpd["attributes"]))

        mean_attr = {a: statistics.mean(f[f"anchor_{a}"] for f in finals) for a in GROWTH}
        top3 = set(_cpu_reference_top3(pos))
        top_mean = statistics.mean(mean_attr[a] for a in top3)
        # Neglected = on-weight attrs the CPU base leaves at 0 for this position.
        from BackEnd.api.franchise_routes import _CPU_REFERENCE_BASE_BY_POS
        base = _CPU_REFERENCE_BASE_BY_POS[pos]
        neglected = [a for a in GROWTH if base.get(a, 0) == 0 and a not in top3]
        if neglected:
            neg_mean = statistics.mean(mean_attr[a] for a in neglected)
            assert top_mean > neg_mean, (
                f"{pos}: reference top-3 mean {top_mean:.0f} should beat neglected "
                f"{neg_mean:.0f} — coaching must still move shape."
            )
        if pos == "C":
            # Collapse-guard: reference CPU keeps a token SC unit so scoring does not rot to
            # the old ~26 live bug. Bound relaxed 35 → 30 for free-will (the additive offseason
            # no longer inflates attributes onto the 2× ladder, so absolute levels sit lower;
            # 30 still catches a genuine collapse well above the 26 floor).
            assert mean_attr["SC"] > 30, f"C mean scoring {mean_attr['SC']:.0f}"


def test_decay_clamps_to_weight_scaled_floor():
    """Floors bind at decay (§5 / §10.2) — a below-floor attr is raised, not left soft."""
    from BackEnd.constants.training_shape import apply_floor_clamp_to_anchors, floor_need, core12_mean
    from BackEnd.models.training_execution_v2 import apply_pre_training_conditions

    attrs = {a: 50 for a in GROWTH}
    attrs["ID"] = 5
    for a in GROWTH:
        attrs[f"anchor_{a}"] = attrs[a]
    player = {
        "_id": "p", "attributes": attrs, "year": "sophomore",
        "position_intent": "C", "training_position": "C",
    }
    need = floor_need("C", "ID", core12_mean(attrs))
    assert need > 5
    apply_pre_training_conditions([player], {})
    assert player["attributes"]["anchor_ID"] >= need
    assert player["attributes"]["ID"] >= need
