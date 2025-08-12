import types
from tests.test_utils import build_mock_game
from BackEnd.utils.shared import record_team_points


def test_turn_result_includes_score_without_scoring():
    game = build_mock_game()
    tm = game.turn_manager

    def fake_no_score():
        return {
            "result_type": "MISS",
            "ball_handler": game.offense_team.lineup["PG"],
            "shooter": game.offense_team.lineup["PG"],
            "screener": game.offense_team.lineup["SG"],
            "passer": game.offense_team.lineup["SG"],
            "defender": game.defense_team.lineup["PG"],
            "text": "miss",
            "possession_flips": True,
            "time_elapsed": 24,
        }

    tm.resolve_half_court_offense = types.MethodType(lambda self: fake_no_score(), tm)
    result = tm.run_micro_turn()

    assert "score" in result
    assert result["score"][game.home_team.name] == 0
    assert result["score"][game.away_team.name] == 0


def test_scoring_turn_includes_metadata_and_score():
    game = build_mock_game()
    tm = game.turn_manager

    def fake_score():
        record_team_points(game, game.offense_team, 2)
        return {
            "result_type": "MAKE",
            "ball_handler": game.offense_team.lineup["PG"],
            "shooter": game.offense_team.lineup["PG"],
            "screener": game.offense_team.lineup["SG"],
            "passer": game.offense_team.lineup["SG"],
            "defender": game.defense_team.lineup["PG"],
            "text": "scores",
            "possession_flips": True,
            "time_elapsed": 24,
            "points": 2,
            "scoring_team": game.offense_team.name,
        }

    tm.resolve_half_court_offense = types.MethodType(lambda self: fake_score(), tm)
    result = tm.run_micro_turn()

    assert result["score"][game.home_team.name] == 2
    assert result.get("points") == 2
    assert result.get("scoring_team") == game.home_team.name


def test_turn_payload_includes_clock_quarter_fouls():
    game = build_mock_game()
    tm = game.turn_manager

    def fake_turn_with_foul():
        # Record a defensive foul on the away team
        game.defense_team.record_team_foul()
        return {
            "result_type": "FOUL",
            "ball_handler": game.offense_team.lineup["PG"],
            "shooter": game.offense_team.lineup["PG"],
            "screener": game.offense_team.lineup["SG"],
            "passer": game.offense_team.lineup["SG"],
            "defender": game.defense_team.lineup["PG"],
            "text": "foul",
            "possession_flips": False,
            "time_elapsed": 30,
        }

    tm.resolve_half_court_offense = types.MethodType(lambda self: fake_turn_with_foul(), tm)
    result = tm.run_micro_turn()

    assert result["clock"] == "7:30"
    assert result["quarter"] == 1
    assert result["homeFouls"] == 0
    assert result["awayFouls"] == 1
