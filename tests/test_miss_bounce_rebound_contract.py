"""MISS/BLOCK schema bounce must carry rebound metadata before DREB promotion."""

from tests.test_fcp_dreb_promotion import (
    _assert_promotes_to_discrete_dreb,
    _miss_with_loose_ball,
    _seed_player_ids_and_coords,
)
from tests.test_utils import build_mock_game

import random

import pytest


@pytest.fixture(autouse=True)
def _seed_rng_for_determinism():
    # These tests exercise RNG-driven resolution (simulate_macro_turn), which made
    # them order-flaky (passed in isolation, failed in some batch orders). Seed the
    # global stream before each test so every run is identical, regardless of what
    # earlier tests consumed. NOTE: re-pick if RNG consumption in the path changes.
    random.seed(0)
    yield


def test_repair_restores_rebound_fields_from_game_state():
    game = build_mock_game()
    _seed_player_ids_and_coords(game)
    rebounder = game.defense_team.lineup["C"]
    game.game_state["last_rebound"] = "DREB"
    game.game_state["last_rebounder"] = rebounder
    game.game_state["offensive_state"] = "HCO"

    miss = {
        "current_turn": "HCO",
        "result_type": "MISS",
        "ball_bounce_x": 80.0,
        "ball_bounce_y": 18.0,
        "animation_steps": [{"end": {"ball": {"coords": {"x": 80, "y": 18}}}}],
    }

    game._repair_miss_bounce_rebound_contract(miss)

    assert miss["rebounderId"] == rebounder.player_id
    assert miss["rebound_type"] == "DREB"
    assert miss["next_play_type"] == "HCO"


def test_repair_skips_quarter_ending_turns():
    game = build_mock_game()
    _seed_player_ids_and_coords(game)
    rebounder = game.defense_team.lineup["C"]
    game.game_state["last_rebound"] = "DREB"
    game.game_state["last_rebounder"] = rebounder

    miss = {
        "current_turn": "HCO",
        "result_type": "MISS",
        "quarter_ends_after": True,
        "ball_bounce_x": 80.0,
        "ball_bounce_y": 18.0,
    }

    game._repair_miss_bounce_rebound_contract(miss)

    assert "rebounderId" not in miss
    assert "rebound_type" not in miss


def test_repair_enables_dreb_promotion(monkeypatch):
    game = build_mock_game()
    _seed_player_ids_and_coords(game)
    game.game_state["offensive_state"] = "HCO"
    game.game_state["time_remaining"] = 480
    game.game_state["shot_clock_remaining"] = 24
    game.offense_team = game.home_team
    game.defense_team = game.away_team

    rebounder = game.defense_team.lineup["C"]
    shooter = game.offense_team.lineup["SG"]
    defender = game.defense_team.lineup["SG"]
    game.game_state["last_rebound"] = "DREB"
    game.game_state["last_rebounder"] = rebounder

    hco_miss = _miss_with_loose_ball(
        game,
        current_turn="HCO",
        next_play_type="HCO",
        rebounder=rebounder,
        shooter=shooter,
        defender=defender,
    )
    hco_miss.pop("rebounderId", None)
    hco_miss.pop("rebound_type", None)
    hco_miss.pop("next_play_type", None)

    def run_micro_turn():
        game._repair_miss_bounce_rebound_contract(hco_miss)
        hco_miss["next_turn"] = game.determine_next_turn(hco_miss)
        return hco_miss

    monkeypatch.setattr(game.turn_manager, "run_micro_turn", run_micro_turn)

    result = game.simulate_macro_turn()

    assert result is hco_miss
    assert result["rebounderId"] == rebounder.player_id
    assert result["rebound_type"] == "DREB"
    _assert_promotes_to_discrete_dreb(game, hco_miss, rebounder, "HCO")
