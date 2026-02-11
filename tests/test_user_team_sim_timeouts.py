import pytest

from tests.test_utils import build_mock_game


def _give_player_fouls(player, n):
    for _ in range(n):
        player.record_stat("F")


def test_user_team_timeout_logic_only_runs_in_full_sim():
    """
    Regression guard:
    - In turn-by-turn (Play Quarter), user team must NOT auto-call timeouts.
    - In full simulation (Sim Quarter / Sim Full Game), user team SHOULD be evaluated by the
      same timeout logic (silently inside the sim).
    """
    game = build_mock_game()

    # Treat home as the user team for this test.
    game.home_team.is_user_team = True
    game.away_team.is_user_team = False

    game.quarter = 1
    game.game_state["time_remaining"] = 480

    # Trigger a Q1 100% foul condition for the home team (active lineup only).
    _give_player_fouls(game.home_team.lineup["PG"], 3)

    # Play Quarter (turn-by-turn): should be blocked for user team.
    game.game_state["_is_full_simulation"] = False
    assert game.turn_manager.should_computer_call_timeout(game.home_team, "SIDE_INBOUND") is False

    # Full simulation: should be allowed (same logic as computer teams).
    game.game_state["_is_full_simulation"] = True
    assert game.turn_manager.should_computer_call_timeout(game.home_team, "SIDE_INBOUND") is True

