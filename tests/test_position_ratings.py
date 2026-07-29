"""Tests for the recalibrated position-rating model (design §3.6).

RT = attribute weighted mean × multiplicative height fitness. One table for
everyone (no recruit profile). Lower clamp 1, uncapped above.
"""

import math

import pytest

from BackEnd.utils.position_ratings import (
    HEIGHT_FITNESS,
    HEIGHT_FITNESS_CAP,
    HEIGHT_FITNESS_FLOOR,
    POSITION_WEIGHTS,
    compute_position_ratings,
    height_fitness,
)


def test_weight_tables_sum_to_one():
    for pos, weights in POSITION_WEIGHTS.items():
        assert math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9), pos


def test_no_height_term_in_weight_tables():
    # Height is a multiplier now, never a weighted attribute.
    for weights in POSITION_WEIGHTS.values():
        assert "height" not in weights


def test_height_fitness_peaks_at_ideal():
    for pos, (ideal, _, _) in HEIGHT_FITNESS.items():
        assert math.isclose(height_fitness(pos, ideal), 1.0)


def test_height_fitness_asymmetric_penalty():
    # C falls off fast when short, barely when tall.
    assert height_fitness("C", 80) < height_fitness("C", 85)
    # PG falls off fast when tall, barely when short.
    assert height_fitness("PG", 84) < height_fitness("PG", 70)


def test_height_fitness_floor_and_cap():
    # A guard-height player is heavily gated out of centre but floored at 0.50.
    assert height_fitness("C", 66) == HEIGHT_FITNESS_FLOOR
    # Fitness never exceeds the cap and never drops below the floor.
    for pos in POSITION_WEIGHTS:
        for h in range(60, 92):
            assert HEIGHT_FITNESS_FLOOR <= height_fitness(pos, h) <= HEIGHT_FITNESS_CAP


def test_rt_equals_mean_times_fitness():
    player = {"height": 82, "attributes": {k: 100 for k in
              ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "IQ", "FT")}}
    # mean of all-100 weighted attrs is 100; C fitness at 82 = 1 - 0.06*0.5 = 0.97.
    assert compute_position_ratings(player)["C"] == round(100 * height_fitness("C", 82))


def test_rt_is_uncapped_above_100():
    player = {"height": 82, "attributes": {k: 120 for k in POSITION_WEIGHTS["C"]}}
    assert compute_position_ratings(player)["C"] > 100


def test_rt_lower_clamp_is_one():
    player = {"height": 60, "attributes": {}}
    for rating in compute_position_ratings(player).values():
        assert rating >= 1


def test_height_gates_short_center_toward_guard():
    # Balanced attributes, guard height: PG should out-rate C purely on fitness.
    player = {"height": 70, "attributes": {k: 60 for k in
              ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "IQ", "FT")}}
    ratings = compute_position_ratings(player)
    assert ratings["PG"] > ratings["C"]


def test_no_profile_parameter():
    # The recruit profile is gone: a recruit's RT must not differ from a player's.
    player = {"height": 78, "attributes": {"SC": 50, "SH": 50, "RB": 50, "ST": 50}}
    with pytest.raises(TypeError):
        compute_position_ratings(player, profile="recruit")  # type: ignore[call-arg]
