"""Permanent suite for the player-development shape framework (§10).

Shape-dispersion lives HERE — not as a follow-up. Every fit / floor / camp /
offseason parameter was chosen against shape; a suite that can only see level
will undo the next tuning pass.
"""
from __future__ import annotations

import math
import random

from BackEnd.constants.training_shape import (
    CAMP_GAIN_SCALE,
    CAMP_WEEKS,
    CORE_12,
    POSITIONS,
    TRAINING_COST_PHYSICAL_ZEROS,
    TRAINING_COST_ZERO,
    gain_divisor_matrix,
    floor_violations,
    is_camp_week,
    training_attr_gain_divisor,
)
from BackEnd.utils import player_development as dev
from BackEnd.utils import player_generation as gen


# ── Gain-divisor matrix locks ─────────────────────────────────────────────────

def test_gain_divisor_matrix_ag_and_st_monotonicity():
    """AG is less effective as players get bigger; ST more effective."""
    ag = [training_attr_gain_divisor(p, "AG") for p in POSITIONS]
    st = [training_attr_gain_divisor(p, "ST") for p in POSITIONS]
    assert ag == sorted(ag), f"AG not ordered PG→C: {ag}"
    assert st == sorted(st, reverse=True), f"ST not ordered PG→C desc: {st}"


def test_gain_divisor_matrix_walls_only_on_explicit_zeros():
    matrix = gain_divisor_matrix()
    for pos in POSITIONS:
        zeros = TRAINING_COST_PHYSICAL_ZEROS[pos]
        for a in CORE_12:
            c = matrix[pos][a]
            if a in zeros:
                assert c == TRAINING_COST_ZERO, f"{pos}/{a} wall missing"
            else:
                assert c <= 3.0 + 1e-9, f"{pos}/{a} over derived cap: {c}"


def test_od_and_sh_are_not_size_ordered():
    """Documented exceptions — perimeter D peaks at the wing; shooting has no size order."""
    od = [training_attr_gain_divisor(p, "OD") for p in POSITIONS]
    sh = [training_attr_gain_divisor(p, "SH") for p in POSITIONS]
    assert od != sorted(od) and od != sorted(od, reverse=True)
    assert sh != sorted(sh) and sh != sorted(sh, reverse=True)
    assert od[2] == min(od), "SF should be cheapest OD (wing peak)"


def test_camp_constants_locked():
    assert CAMP_WEEKS == 1
    assert CAMP_GAIN_SCALE == 1.4
    assert is_camp_week(1) and not is_camp_week(2) and not is_camp_week(27)


def test_floors_refuse_starved_id_big():
    """Pathology: rim-protector ID=8 at PF/C must violate the weight-scaled floor."""
    for pos in ("PF", "C"):
        attrs = {a: 50 for a in CORE_12}
        attrs["ID"] = 8
        viols = floor_violations(pos, attrs)
        assert any(a == "ID" for a, _, _ in viols), f"{pos} ID=8 should refuse: {viols}"


# ── Shape dispersion (the metric that signs off this framework) ───────────────

def _shape_vec(attrs: dict) -> list[float]:
    vals = [float(attrs.get(a, 0) or 0) for a in CORE_12]
    mean = sum(vals) / len(vals) if vals else 1.0
    if mean <= 1e-9:
        return [0.0] * len(CORE_12)
    return [v / mean for v in vals]


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return 1.0 - (dot / (na * nb))


def _mean_pairwise_shape_distance(shapes: list[list[float]]) -> float:
    if len(shapes) < 2:
        return 0.0
    dists = []
    for i in range(len(shapes)):
        for j in range(i + 1, len(shapes)):
            dists.append(_cosine_distance(shapes[i], shapes[j]))
    return sum(dists) / len(dists)


def test_offseason_level_only_preserves_within_position_shape_dispersion():
    """Retiring the α-attractor: three level-only offseasons must not collapse
    within-position pairwise shape distance the way α=0.55 did (career ~0.245).

    Generate varied JH shapes per position, develop three rungs with no in-season
    training (identity-only path), and require career shape retention of pairwise
    distance ≥ 0.55 — the framework force-split target.
    """
    assert dev.OFFSEASON_ATTRACTOR_ALPHA == 0.0

    rng = random.Random(20260807)
    N = 24
    for pos in POSITIONS:
        shapes_t0 = []
        shapes_t3 = []
        for i in range(N):
            # Distinct CH seeds → distinct growth profiles; attribute draws vary too.
            jh = gen.generate_player(pos, "JH", "Average", random.Random(1000 + i * 17 + hash(pos) % 97))
            fpd = {
                "player_id": f"{pos}-{i}",
                "meta": {
                    "year": "JH",
                    "height": jh["height"],
                    "weight": jh["weight"],
                },
                "attributes": dict(jh["attributes"]),
                "position_ratings": dict(jh["position_ratings"]),
                "entry_tier": "Average",
                "position_intent": pos,
                "training_position": pos,
                "potential_factor": 1.0,
            }
            shapes_t0.append(_shape_vec(fpd["attributes"]))
            career_rng = random.Random(5000 + i)
            for y in ("freshman", "sophomore", "junior"):
                out = dev.develop_rollover(fpd, y, career_rng, season_allocation=None)
                fpd["attributes"] = out["attributes"]
                fpd["position_ratings"] = out["position_ratings"]
                fpd["development"] = out["development"]
                fpd["meta"]["height"] = out["height"]
                fpd["meta"]["weight"] = out["weight"]
                fpd["entry_tier"] = out["entry_tier"]
                fpd["meta"]["year"] = y
            shapes_t3.append(_shape_vec(fpd["attributes"]))

        d0 = _mean_pairwise_shape_distance(shapes_t0)
        d3 = _mean_pairwise_shape_distance(shapes_t3)
        # One-step retention over 3 develops ≈ (d3/d0); career-style cube not needed
        # here — we assert the ratio itself stays near identity (level-only).
        retention = (d3 / d0) if d0 > 1e-9 else 1.0
        assert retention >= 0.55, (
            f"{pos}: pairwise shape retention {retention:.3f} (d0={d0:.4f}→d3={d3:.4f}) "
            f"collapsed toward the old attractor regime — offseason must be level-only."
        )


def test_attractor_alpha_is_retired():
    assert getattr(dev, "OFFSEASON_ATTRACTOR_ALPHA", None) == 0.0


# ── Along / across shape movement (cosine alone conflates them) ───────────────

def test_decompose_shape_delta_separates_sharpening_from_conversion():
    """Along = more of the same peaks; across = orthogonal identity change."""
    from BackEnd.utils.shape_movement import decompose_shape_delta

    def _unit_mean(raw):
        m = sum(raw) / len(raw)
        return [x / m for x in raw]

    # Start already specialised on dim 0.
    s0 = _unit_mean([2.2, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8])
    assert abs(sum(s0) / len(s0) - 1.0) < 1e-9

    # Sharpen further on the same peak.
    s_sharp = _unit_mean([3.0, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7])
    d_sharp = decompose_shape_delta(s0, s_sharp)
    assert d_sharp["along"] > 0.0
    assert d_sharp["along_share"] > d_sharp["across_share"]

    # Convert: flatten the old peak, raise a different one.
    s_conv = _unit_mean([0.7, 0.7, 0.7, 3.0, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7])
    d_conv = decompose_shape_delta(s0, s_conv)
    assert d_conv["across"] > d_sharp["across"]
    assert d_conv["across_share"] > d_conv["along_share"]


def test_strategy_across_shape_orders_conversion_above_specialisation():
    """Permanent gate: conversion arms move across-shape more than reference.

    Raw cosine retention is not the ordering key — reference specialises
    (along-shape) and can look "less retentive" than a mild spread. Across-shape
    is the honest "did this coach change who the player is" readout.
    """
    from scripts.s11_framework_baseline_measure import run_arm

    n = 40
    ref = run_arm("reference", n=n)
    mild = run_arm("mild", n=n)
    moderate = run_arm("moderate", n=n)
    extreme = run_arm("extreme", n=n)

    assert extreme["mean_across_shape"] > moderate["mean_across_shape"] > ref["mean_across_shape"]
    # Mild preserves more than reference sharpening on the conversion axis.
    assert mild["mean_across_shape"] <= moderate["mean_across_shape"]
    # Reference should show real along-shape (specialisation), not a null.
    assert ref["mean_along_shape"] > 0.0
