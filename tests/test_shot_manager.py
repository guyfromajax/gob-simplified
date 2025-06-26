from tests.test_utils import build_mock_game
from BackEnd.models.shot_manager import ShotManager


def test_resolve_shot_returns_make_or_miss():
    game = build_mock_game()
    shot_manager = ShotManager(game)

    roles = {
        "shooter": game.offense_team.lineup["PG"],
        "screener": game.offense_team.lineup["SG"],
        "passer": game.offense_team.lineup["SF"],
        "defender": game.defense_team.lineup["PG"]
    }

    result = shot_manager.resolve_shot(roles)

    assert isinstance(result, dict)
    assert "result_type" in result
    assert result["result_type"] in ["MAKE", "MISS"]
    assert "shooter" in result


def test_resolve_fast_break_shot_works():
    game = build_mock_game()
    shot_manager = ShotManager(game)

    fb_roles = {
        "shooter": game.offense_team.lineup["PG"],
        "passer": game.offense_team.lineup["SG"],
        "defense": [game.defense_team.lineup["PG"], game.defense_team.lineup["SG"]]
    }
    result = shot_manager.resolve_fast_break_shot(fb_roles)

    assert "result_type" in result
    VALID_RESULTS = {"MAKE", "MISS", "FOUL", "TURNOVER", "DEAD BALL"}
    assert result["result_type"] in VALID_RESULTS


