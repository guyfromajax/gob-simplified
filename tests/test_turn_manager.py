from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.models.player import Player
from BackEnd.constants import POSITION_LIST, STRATEGY_CALL_DICTS, PLAYCALLS

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

def test_strategy_calls_are_set(mock_game_manager):
    tm = TurnManager(mock_game_manager)
    tm.set_strategy_calls()
    off_team = mock_game_manager.home_team
    def_team = mock_game_manager.away_team

    # Use the actual setting instead of hardcoding
    tempo_setting = mock_game_manager.game_state["strategy_settings"][off_team]["tempo"]
    aggression_setting = mock_game_manager.game_state["strategy_settings"][def_team]["aggression"]
    calls = mock_game_manager.game_state["strategy_calls"]

    assert calls[off_team]["tempo_call"] in STRATEGY_CALL_DICTS["tempo"][tempo_setting]
    assert calls[def_team]["aggression_call"] in STRATEGY_CALL_DICTS["aggression"][aggression_setting]


def test_playcalls_are_set(mock_game_manager):
    tm = TurnManager(mock_game_manager)
    calls = tm.set_playcalls()
    assert calls["offense"] in PLAYCALLS
    assert calls["defense"] in ["Man", "Zone"]




 