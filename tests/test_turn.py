
from tests.test_utils import build_mock_game

def test_assign_roles_outputs_player_objects():
    game = build_mock_game()
    roles = game.turn_manager.assign_roles()

    assert roles["shooter"] is not None
    assert roles["screener"] is not None
    assert roles["ball_handler"] is not None
    assert hasattr(roles["shooter"], "record_stat")


def test_turn_returns_valid_result():
    game = build_mock_game()
    result = game.simulate_macro_turn()

    VALID_RESULTS = {"MAKE", "MISS", "FOUL", "TURNOVER", "DEAD BALL"}
    assert result["result_type"] in VALID_RESULTS