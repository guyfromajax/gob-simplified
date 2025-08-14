from tests.test_utils import build_mock_game
from BackEnd.engine.phase_resolution import resolve_free_throw_logic


def _setup_game(one_and_one: bool):
    game = build_mock_game()
    shooter = game.offense_team.lineup["PG"]
    game.game_state.update({
        "offensive_state": "FREE_THROW",
        "shooter": shooter,
        "last_ball_handler": shooter,
        "free_throws_remaining": 1,
        "one_and_one": one_and_one,
    })
    # ensure every FT is made
    game.offense_team.team_attributes["ft_shot_threshold"] = 0
    return game, shooter


def test_standard_free_throw_records_points_and_totals():
    game, shooter = _setup_game(one_and_one=False)
    result = resolve_free_throw_logic(game)

    assert result["shooter"] is shooter
    assert result["points"] == 1
    assert result["scoring_team"] == game.offense_team.name
    assert game.score[game.offense_team.name] == 1
    assert shooter.stats["game"]["FTM"] == 1
    assert shooter.stats["game"]["FTA"] == 1
    assert shooter.stats["game"]["PTS"] == 1


def test_one_and_one_front_end_records_points_and_totals():
    game, shooter = _setup_game(one_and_one=True)
    result = resolve_free_throw_logic(game)

    assert result["shooter"] is shooter
    assert result["points"] == 1
    assert result["scoring_team"] == game.offense_team.name
    assert game.score[game.offense_team.name] == 1
    assert shooter.stats["game"]["FTM"] == 1
    assert shooter.stats["game"]["FTA"] == 1
    assert shooter.stats["game"]["PTS"] == 1
    assert game.game_state["free_throws_remaining"] == 1
    assert game.game_state["one_and_one"] is False
