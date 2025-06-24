from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.models.player import Player
from BackEnd.constants import POSITION_LIST

def test_turn_manager_assign_roles_outputs_roles_dict(mock_game_manager):
    tm = TurnManager(mock_game_manager)
    roles = tm.assign_roles("Base")

    assert isinstance(roles, dict)
    for role in ["shooter", "passer", "screener", "defender"]:
        assert role in roles

def test_turn_manager_assign_roles_outputs_valid_positions(mock_game_manager):
    tm = TurnManager(mock_game_manager)
    roles = tm.assign_roles("Base")

    valid_players = list(mock_game_manager.game_state["players"]["Team A"].values()) + list(mock_game_manager.game_state["players"]["Team B"].values())
    for key in ["shooter", "passer", "screener", "defender"]:
        assert roles[key] in valid_players or roles[key] is None
        assert isinstance(roles[key], Player) or roles[key] is None

def test_turn_manager_run_turn_executes(mock_game_manager):
    tm = TurnManager(mock_game_manager)
    result = tm.run_turn()

    assert isinstance(result, dict)
    assert "result_type" in result

def test_turn_manager_resolve_shot_returns_score(mock_game_manager):
    tm = TurnManager(mock_game_manager)
    roles = tm.assign_roles("Base")
    sm = ShotManager(mock_game_manager.game_state)
    result = sm.resolve_shot(roles)

    assert isinstance(result, dict)
    assert "shot_score" in result

def test_turn_manager_resolve_shot_returns_valid_result_type(mock_game_manager):
    tm = TurnManager(mock_game_manager)
    roles = tm.assign_roles("Base")
    sm = ShotManager(mock_game_manager.game_state)
    result = sm.resolve_shot(roles)

    assert result["result_type"] in ["MAKE", "MISS", "BLOCK", "TURNOVER"]



 