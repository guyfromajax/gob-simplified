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
    TRAINING_GAIN_PERCENTAGES,
    TRAINING_GAIN_INVARIANT_EXCEPTIONS,
    TRAINING_GAIN_UNIVERSALS,
    TRAINING_PHYSICAL_WALLS,
    gain_percentage_matrix,
    floor_violations,
    is_camp_week,
    training_attr_gain_multiplier,
)
from BackEnd.utils import player_development as dev
from BackEnd.utils import player_generation as gen


# ── Direct gain-percentage invariants ─────────────────────────────────────────

def test_cross_position_gain_orderings_are_locked():
    """Big-player attrs rise PG→C; perimeter movement/creation falls."""
    for attr in ("RB", "ID"):
        values = [TRAINING_GAIN_PERCENTAGES[p][attr] for p in POSITIONS]
        assert values == sorted(values) and values[0] < values[-1], f"{attr}: {values}"
    for attr in ("BH", "PS", "AG"):
        values = [TRAINING_GAIN_PERCENTAGES[p][attr] for p in POSITIONS]
        assert values == sorted(values, reverse=True) and values[0] > values[-1], f"{attr}: {values}"

    strength = [TRAINING_GAIN_PERCENTAGES[p]["ST"] for p in POSITIONS]
    violations = {
        (POSITIONS[i], POSITIONS[i + 1])
        for i in range(len(POSITIONS) - 1)
        if strength[i] > strength[i + 1]
    }
    assert violations == set(TRAINING_GAIN_INVARIANT_EXCEPTIONS["strength_ordering"])


def test_every_selectable_training_target_totals_the_same():
    totals = {pos: sum(TRAINING_GAIN_PERCENTAGES[pos].values()) for pos in POSITIONS}
    assert set(totals.values()) == {808}, totals


def test_25_percent_is_reserved_for_documented_physical_walls():
    matrix = gain_percentage_matrix()
    named_exceptions = set(TRAINING_GAIN_INVARIANT_EXCEPTIONS["nonphysical_25_percent"])
    actual_nonphysical = set()
    for pos in POSITIONS:
        for a in CORE_12:
            if matrix[pos][a] == 25.0 and a not in TRAINING_PHYSICAL_WALLS[pos]:
                actual_nonphysical.add((pos, a))
            if a in TRAINING_PHYSICAL_WALLS[pos]:
                assert matrix[pos][a] == 25.0, f"documented wall changed: {pos}/{a}"
    assert actual_nonphysical == named_exceptions


def test_universals_are_100_percent_at_every_position():
    for pos in POSITIONS:
        for attr in TRAINING_GAIN_UNIVERSALS:
            assert TRAINING_GAIN_PERCENTAGES[pos][attr] == 100.0, f"{pos}/{attr}"


def test_od_and_sh_are_not_size_ordered():
    """Documented exceptions — perimeter D peaks at the wing; shooting has no size order."""
    od = [training_attr_gain_multiplier(p, "OD") for p in POSITIONS]
    sh = [training_attr_gain_multiplier(p, "SH") for p in POSITIONS]
    assert od != sorted(od) and od != sorted(od, reverse=True)
    assert sh != sorted(sh) and sh != sorted(sh, reverse=True)
    assert od[2] == max(od), "SF should receive full-value OD (wing peak)"


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
