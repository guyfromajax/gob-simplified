from tests.test_utils import build_mock_game
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.constants import STRATEGY_CALL_DICTS, PLAYCALLS
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
    assert "shot_score" in result


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



 