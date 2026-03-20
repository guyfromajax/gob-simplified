"""Tests for Home Crowd Factor (in-game only)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from BackEnd.constants import FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE
from BackEnd.utils import home_crowd as hc


def test_band_weights_sum_to_100():
    bands = [
        ([30, 40, 15, 10, 5], "7-10"),
        ([20, 30, 25, 15, 10], "11-15"),
        ([10, 20, 30, 20, 20], "16-20"),
        ([5, 15, 20, 30, 30], "21-25"),
    ]
    for weights, label in bands:
        assert sum(weights) == 100, f"band {label} should sum to 100, got {sum(weights)}"


@patch("BackEnd.utils.home_crowd.random.choices")
def test_roll_home_crowd_factor_uses_expected_weights(mock_choices):
    mock_choices.return_value = [3]
    assert hc.roll_home_crowd_factor(9) == 3
    args, kwargs = mock_choices.call_args
    assert kwargs["weights"] == [30, 40, 15, 10, 5]

    mock_choices.return_value = [4]
    assert hc.roll_home_crowd_factor(22) == 4
    _, kwargs2 = mock_choices.call_args
    assert kwargs2["weights"] == [5, 15, 20, 30, 30]


def test_shot_threshold_deltas_by_factor():
    assert hc._shot_threshold_deltas_for_factor(1) == (0, 0)
    assert hc._shot_threshold_deltas_for_factor(2) == (0, 0)
    assert hc._shot_threshold_deltas_for_factor(3) == (25, 0)
    assert hc._shot_threshold_deltas_for_factor(4) == (50, 0)
    assert hc._shot_threshold_deltas_for_factor(5) == (50, -50)


def test_home_crowd_shot_threshold_delta_for_offense():
    game = MagicMock()
    game.game_state = {
        "home_crowd_away_shot_threshold_delta": 50,
        "home_crowd_home_shot_threshold_delta": -50,
    }
    away = MagicMock()
    away.is_home_team = False
    home = MagicMock()
    home.is_home_team = True
    assert hc.home_crowd_shot_threshold_delta_for_offense(away, game) == 50
    assert hc.home_crowd_shot_threshold_delta_for_offense(home, game) == -50


def test_effective_ft_second_chance():
    game = MagicMock()
    game.game_state = {"home_crowd_factor": 4}

    home_shooter = MagicMock()
    home_shooter.is_home_team = True
    assert (
        hc.effective_ft_miss_to_make_second_chance(game, home_shooter)
        == FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE
    )

    away = MagicMock()
    away.is_home_team = False
    game.game_state["home_crowd_factor"] = 1
    assert (
        hc.effective_ft_miss_to_make_second_chance(game, away)
        == FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE
    )
    game.game_state["home_crowd_factor"] = 2
    assert hc.effective_ft_miss_to_make_second_chance(game, away) == pytest.approx(0.3)
    game.game_state["home_crowd_factor"] = 3
    assert hc.effective_ft_miss_to_make_second_chance(game, away) == pytest.approx(0.3)
    game.game_state["home_crowd_factor"] = 4
    assert hc.effective_ft_miss_to_make_second_chance(game, away) == pytest.approx(0.2)
    game.game_state["home_crowd_factor"] = 5
    assert hc.effective_ft_miss_to_make_second_chance(game, away) == pytest.approx(0.2)


def test_restore_home_crowd_from_saved_overwrites():
    gs = {"home_crowd_factor": 1, "home_crowd_away_shot_threshold_delta": 0, "home_crowd_home_shot_threshold_delta": 0}
    saved = {
        "home_crowd_factor": 5,
        "home_crowd_away_shot_threshold_delta": 50,
        "home_crowd_home_shot_threshold_delta": -50,
    }
    hc.restore_home_crowd_from_saved(gs, saved)
    assert gs["home_crowd_factor"] == 5
    assert gs["home_crowd_away_shot_threshold_delta"] == 50
    assert gs["home_crowd_home_shot_threshold_delta"] == -50
