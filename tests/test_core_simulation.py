from tests.test_utils import build_mock_game
from BackEnd.models.shot_manager import ShotManager
from BackEnd.engine.phase_resolution import resolve_fast_break_logic

# Test: ShotManager.resolve_shot
def test_resolve_shot_basic():
    game = build_mock_game()
    shot_manager = ShotManager(game)
    roles = {
        "shooter": game.offense_team.lineup["PG"],
        "screener": game.offense_team.lineup["SG"],
        "passer": game.offense_team.lineup["SF"],
        "defender": game.defense_team.lineup["PG"]
    }

    result = shot_manager.resolve_shot(roles)
    assert "result_type" in result
    assert result["result_type"] in ["MAKE", "MISS"]


# Test: phase_resolution.resolve_fast_break_logic
def test_resolve_fast_break_logic_runs():
    game = build_mock_game()
    game.game_state["last_rebound"] = "DREB"
    game.game_state["last_rebounder"] = game.offense_team.lineup["C"]

    result = resolve_fast_break_logic(game)

    assert "result_type" in result
    VALID_RESULTS = {"MAKE", "MISS", "FOUL", "TURNOVER", "DEAD BALL"}
    assert result["result_type"] in VALID_RESULTS



# Test: TurnManager.assign_roles
def test_assign_roles_outputs_roles_dict():
    game = build_mock_game()
    roles = game.turn_manager.assign_roles()
    assert isinstance(roles, dict)
    assert "shooter" in roles
    assert "pass_chain" in roles
    assert "defender" in roles
