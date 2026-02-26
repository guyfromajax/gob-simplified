from tests.test_utils import build_mock_game
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.constants import STRATEGY_CALL_DICTS, PLAYCALLS, ACTIONS
from BackEnd.utils.shared import get_player_position


def test_turn_manager_assign_roles_outputs_roles_dict():
    game = build_mock_game()
    tm = TurnManager(game)
    roles = tm.assign_roles()
    assert isinstance(roles, dict)
    for role in ["shooter", "passer", "screener", "defender"]:
        assert role in roles


def test_turn_manager_assign_roles_outputs_valid_objects():
    game = build_mock_game()
    tm = TurnManager(game)
    roles = tm.assign_roles()
    for role in ["shooter", "passer", "screener", "defender"]:
        player = roles.get(role)
        assert player is None or player.get_name().startswith("Lancaster") or player.get_name().startswith("Bentley-Truman")


def test_assign_roles_includes_shoot_action():
    game = build_mock_game()
    game.offense_team.strategy_calls["tempo_call"] = "slow"
    tm = TurnManager(game)
    roles = tm.assign_roles()

    step_actions = [
        info["action"]
        for step in roles["steps"]
        for info in step["pos_actions"].values()
    ]
    assert ACTIONS["SHOOT"] in step_actions

    timeline_actions = [
        action
        for actions in roles["action_timeline"].values()
        for _, action, _ in actions
    ]
    assert ACTIONS["SHOOT"] in timeline_actions


def test_turn_manager_run_micro_turn_executes():
    game = build_mock_game()
    tm = TurnManager(game)
    result = tm.run_micro_turn()
    assert isinstance(result, dict)
    assert "result_type" in result


def test_turn_manager_resolve_shot_returns_score():
    game = build_mock_game()
    sm = ShotManager(game)
    roles = {
        "shooter": game.offense_team.lineup["PG"],
        "passer": game.offense_team.lineup["SG"],
        "screener": game.offense_team.lineup["SF"],
        "defender": game.defense_team.lineup["PG"]
    }
    result = sm.resolve_shot(roles)
    assert isinstance(result, dict)


def test_turn_manager_resolve_shot_returns_valid_result_type():
    game = build_mock_game()
    sm = ShotManager(game)
    roles = {
        "shooter": game.offense_team.lineup["PG"],
        "passer": game.offense_team.lineup["SG"],
        "screener": game.offense_team.lineup["SF"],
        "defender": game.defense_team.lineup["PG"]
    }
    result = sm.resolve_shot(roles)
    VALID_RESULTS = {"MAKE", "MISS", "FOUL", "TURNOVER", "DEAD BALL"}
    assert result["result_type"] in VALID_RESULTS



def test_strategy_calls_are_set():
    game = build_mock_game()
    tm = TurnManager(game)
    tm.set_strategy_calls()
    
    off_team = game.offense_team
    def_team = game.defense_team

    assert "tempo_call" in off_team.strategy_calls
    assert "aggression_call" in def_team.strategy_calls



def test_playcalls_are_set():
    game = build_mock_game()
    tm = TurnManager(game)
    calls = tm.set_playcalls()
    assert calls["offense"] in PLAYCALLS
    assert calls["defense"] in ["Man", "Zone"]


def test_turn_result_has_possession_flips():
    game = build_mock_game()
    tm = TurnManager(game)
    result = tm.run_micro_turn()
    assert "possession_flips" in result
    assert isinstance(result["possession_flips"], bool)


def test_turn_result_includes_possession_ids():
    game = build_mock_game()
    tm = TurnManager(game)
    starting_id = game.offense_team.team_id
    result = tm.run_micro_turn()
    assert result["starting_possession_team_id"] == starting_id
    assert result["possession_team_id"] == game.offense_team.team_id


def _init_min_for_players(game):
    """Ensure MIN exists so update_clock_and_possession doesn't KeyError (MockPlayer doesn't set it)."""
    for team in (game.home_team, game.away_team):
        for player in (team.lineup or {}).values():
            if player and isinstance(player.stats.get("game"), dict):
                player.stats["game"].setdefault("MIN", 0)


def test_shot_clock_stops_at_shot_attempt_when_step_timing_present():
    """Shot clock uses game_seconds_at_shot (sum of steps to resolution_step_index), not full turn elapsed."""
    game = build_mock_game()
    _init_min_for_players(game)
    game.game_state["time_remaining"] = 600
    game.game_state["shot_clock_remaining"] = 30
    # Turn: shot at step 1; steps [2, 3, 4] → game_seconds_at_shot = 2+3 = 5, full time_elapsed = 9
    result = {
        "result_type": "MAKE",
        "time_elapsed": 9,
        "current_turn": "HCO",
        "step_clock_seconds": [2, 3, 4],
        "resolution_step_index": 1,
    }
    game.turn_manager.update_clock_and_possession(result)
    # Game clock: full 9 seconds elapsed
    assert result["clock_start"] == 600
    assert result["clock_end"] == 591
    # Shot clock: stopped at shot → only 5 seconds burned (steps 0+1)
    assert result["shot_clock_start"] == 30
    assert result["shot_clock_end"] == 25


def test_shot_clock_uses_full_elapsed_when_no_step_timing():
    """Shot-attempt turn without step_clock_seconds/resolution_step_index falls back to full elapsed."""
    game = build_mock_game()
    _init_min_for_players(game)
    game.game_state["time_remaining"] = 600
    game.game_state["shot_clock_remaining"] = 30
    result = {
        "result_type": "MISS",
        "time_elapsed": 9,
        "current_turn": "FAST_BREAK",
        # no step_clock_seconds / resolution_step_index
    }
    game.turn_manager.update_clock_and_possession(result)
    assert result["clock_start"] == 600
    assert result["clock_end"] == 591
    assert result["shot_clock_start"] == 30
    assert result["shot_clock_end"] == 21  # 30 - 9 (full elapsed)


def test_shot_clock_stops_at_shot_for_shooting_foul_turn():
    """FOUL with free_throws_remaining is treated as shot attempt; shot clock stops at resolution step."""
    game = build_mock_game()
    _init_min_for_players(game)
    game.game_state["time_remaining"] = 600
    game.game_state["shot_clock_remaining"] = 30
    result = {
        "result_type": "FOUL",
        "free_throws_remaining": 2,
        "time_elapsed": 8,
        "current_turn": "HCO",
        "step_clock_seconds": [2, 2, 4],
        "resolution_step_index": 0,
    }
    game.turn_manager.update_clock_and_possession(result)
    # Game seconds at shot = step 0 only = 2
    assert result["shot_clock_start"] == 30
    assert result["shot_clock_end"] == 28
    assert result["clock_end"] == 592


 