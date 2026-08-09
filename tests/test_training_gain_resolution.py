"""Gain-path resolution: distinct point bands + fractional remainder (§10.6)."""
import random
from unittest.mock import patch
import pytest

from BackEnd.models.training_execution_v2 import (
    IN_SEASON_GAIN_SCALE,
    PLAYER_ATTR_GAIN_RANGE_BY_POINTS,
    _apply_player_training_points,
    _apply_scaled_gain_with_remainder,
    _player_attr_gain_range,
)
from BackEnd.constants.training_shape import (
    CAMP_GAIN_SCALE,
    CLASS_GAIN_MULT,
    training_attr_gain_multiplier,
    training_points_spent,
)


def _E(lo, hi):
    return sum(range(lo, hi + 1)) / (hi - lo + 1)


def test_point_bands_are_distinct_and_ascending():
    expectations = []
    for pts in range(1, 6):
        lo, hi = _player_attr_gain_range(pts)
        assert (lo, hi) == PLAYER_ATTR_GAIN_RANGE_BY_POINTS[pts]
        expectations.append(_E(lo, hi))
    assert expectations == sorted(expectations)
    assert len(set(expectations)) == 5
    # Hold max-commitment expected raw so season level does not silently retune.
    assert abs(_E(*PLAYER_ATTR_GAIN_RANGE_BY_POINTS[5]) - 4.5) < 1e-9


def test_fractional_remainder_accumulates_across_weeks():
    # FT is universal, and freshman has a 1.0 class multiplier, isolating the
    # session-scale remainder behavior this test owns.
    player = {"year": "freshman", "attributes": {"anchor_FT": 50, "FT": 50}}
    # Force a raw roll whose scaled gain is sub-integer: 2 × 0.18 = 0.36
    with patch.object(random, "randint", return_value=2):
        _apply_player_training_points(player, "FT", points=1, archetype=None, sub_option=None)
    assert player["attributes"]["anchor_FT"] == 50
    assert abs(player["training_gain_remainders"]["FT"] - 2 * IN_SEASON_GAIN_SCALE) < 1e-9

    with patch.object(random, "randint", return_value=2):
        _apply_player_training_points(player, "FT", points=1, archetype=None, sub_option=None)
    assert player["attributes"]["anchor_FT"] == 50
    assert abs(player["training_gain_remainders"]["FT"] - 4 * IN_SEASON_GAIN_SCALE) < 1e-9

    with patch.object(random, "randint", return_value=2):
        _apply_player_training_points(player, "FT", points=1, archetype=None, sub_option=None)
    # 0.36 × 3 = 1.08 → +1, rem 0.08
    assert player["attributes"]["anchor_FT"] == 51
    assert abs(player["training_gain_remainders"]["FT"] - 0.08) < 1e-9


def test_remainder_helper_banks_fraction_only():
    player = {}
    assert _apply_scaled_gain_with_remainder(player, "SH", 2, 0.18) == 0
    assert abs(player["training_gain_remainders"]["SH"] - 0.36) < 1e-9
    assert _apply_scaled_gain_with_remainder(player, "SH", 4, 0.18) == 1  # 0.36+0.72=1.08
    assert abs(player["training_gain_remainders"]["SH"] - 0.08) < 1e-9


def test_flat_budget_counts_every_notch_as_one_point():
    allocations = {
        "player_drills": {"offense": {"inside": 5, "outside": 4}},
        "general": {"conditioning": 3, "breaks": 2},
        "team_drills": {"offense_install": 5, "scrimmages": 5},
    }
    assert training_points_spent(allocations) == 24


def test_flat_budget_rejects_fractional_notches_even_when_the_sum_is_whole():
    with pytest.raises(ValueError, match="whole numbers"):
        training_points_spent({"player_drills": {"offense": {"inside": 0.5, "outside": 0.5}}})


def test_fit_and_class_are_gain_multipliers_not_budget_prices():
    assert training_attr_gain_multiplier("C", "AG") == 0.25
    assert CLASS_GAIN_MULT["FR"] == 1.0
    assert abs(CLASS_GAIN_MULT["SO"] - (1 / 1.1)) < 1e-12
    assert CLASS_GAIN_MULT["JR"] == 0.8
    assert abs(CLASS_GAIN_MULT["SR"] - (1 / 1.4)) < 1e-12


def test_senior_wall_full_allocation_remains_meaningfully_positive_over_season():
    """Worst stack: minimum raw roll, C agility wall, senior class taper.

    Three camp weeks at 1.4 plus 23 in-season weeks at 0.18 must still bank
    enough persisted fraction to produce four whole attribute points.
    """
    player = {
        "year": "senior",
        "training_position": "C",
        "attributes": {"anchor_AG": 50, "AG": 50},
    }
    with patch.object(random, "randint", return_value=3):
        for _ in range(3):
            _apply_player_training_points(
                player, "AG", points=5, archetype=None, sub_option=None,
                gain_scale=CAMP_GAIN_SCALE,
            )
        for _ in range(23):
            _apply_player_training_points(
                player, "AG", points=5, archetype=None, sub_option=None,
                gain_scale=IN_SEASON_GAIN_SCALE,
            )
    assert player["attributes"]["anchor_AG"] == 54
    assert 0.46 < player["training_gain_remainders"]["AG"] < 0.48
