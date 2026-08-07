"""Gain-path resolution: distinct point bands + fractional remainder (§10.6)."""
import random
from unittest.mock import patch

from BackEnd.models.training_execution_v2 import (
    IN_SEASON_GAIN_SCALE,
    PLAYER_ATTR_GAIN_RANGE_BY_POINTS,
    _apply_player_training_points,
    _apply_scaled_gain_with_remainder,
    _player_attr_gain_range,
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
    player = {"year": "senior", "attributes": {"anchor_SC": 50, "SC": 50}}
    # Force a raw roll whose scaled gain is sub-integer: 2 × 0.18 = 0.36
    with patch.object(random, "randint", return_value=2):
        _apply_player_training_points(player, "SC", points=1, archetype=None, sub_option=None)
    assert player["attributes"]["anchor_SC"] == 50
    assert abs(player["training_gain_remainders"]["SC"] - 2 * IN_SEASON_GAIN_SCALE) < 1e-9

    with patch.object(random, "randint", return_value=2):
        _apply_player_training_points(player, "SC", points=1, archetype=None, sub_option=None)
    assert player["attributes"]["anchor_SC"] == 50
    assert abs(player["training_gain_remainders"]["SC"] - 4 * IN_SEASON_GAIN_SCALE) < 1e-9

    with patch.object(random, "randint", return_value=2):
        _apply_player_training_points(player, "SC", points=1, archetype=None, sub_option=None)
    # 0.36 × 3 = 1.08 → +1, rem 0.08
    assert player["attributes"]["anchor_SC"] == 51
    assert abs(player["training_gain_remainders"]["SC"] - 0.08) < 1e-9


def test_remainder_helper_banks_fraction_only():
    player = {}
    assert _apply_scaled_gain_with_remainder(player, "SH", 2, 0.18) == 0
    assert abs(player["training_gain_remainders"]["SH"] - 0.36) < 1e-9
    assert _apply_scaled_gain_with_remainder(player, "SH", 4, 0.18) == 1  # 0.36+0.72=1.08
    assert abs(player["training_gain_remainders"]["SH"] - 0.08) < 1e-9
