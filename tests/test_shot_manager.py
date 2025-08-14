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
    game.offense_team.team_attributes["shot_threshold"] = 0

    fb_roles = {
        "shooter": game.offense_team.lineup["PG"],
        "passer": game.offense_team.lineup["SG"],
        "defense": [game.defense_team.lineup["PG"], game.defense_team.lineup["SG"]]
    }
    result = shot_manager.resolve_fast_break_shot(fb_roles)

    assert "result_type" in result
    VALID_RESULTS = {"MAKE", "MISS", "FOUL", "TURNOVER", "DEAD BALL"}
    assert result["result_type"] in VALID_RESULTS
    assert result["result_type"] == "MAKE"
    assert result["points"] == 2
    assert result["scoring_team"] == game.offense_team.name


def test_offensive_rebound_putback_updates_stats(monkeypatch):
    game = build_mock_game()
    shot_manager = ShotManager(game)

    shooter = game.offense_team.lineup["PG"]
    rebounder = game.offense_team.lineup["C"]
    defender = game.defense_team.lineup["PG"]

    roles = {"shooter": shooter, "defender": defender}

    # Force an initial miss
    def fake_calc(self, shooter, passer, screener, defender, playcall, defense_call, is_three):
        return 0, None, False, None

    monkeypatch.setattr(ShotManager, "calculate_shot_score", fake_calc)

    # Deterministic rebound outcome: offensive C grabs board
    monkeypatch.setattr("BackEnd.models.shot_manager.choose_rebounder", lambda rebounders, side: "C" if side == "offense" else "PG")
    monkeypatch.setattr("BackEnd.models.shot_manager.calculate_rebound_score", lambda player: 10)

    # Random sequence: no 3PA, no block, offensive rebound, attempt putback
    rand_vals = iter([0.9, 0.99, 0.99, 0.1])
    monkeypatch.setattr("BackEnd.models.shot_manager.random.random", lambda: next(rand_vals))

    # Remove tempo randomness
    monkeypatch.setattr("BackEnd.models.shot_manager.get_time_elapsed", lambda tempo: 0)

    from BackEnd.utils.shared import record_team_points

    def fake_putback(game_param, rebounder_param):
        rebounder_param.record_stat("FGA")
        rebounder_param.record_stat("FGM")
        record_team_points(game_param, game_param.offense_team, 2)
        return {
            "text": " and he scores!",
            "possession_flips": True,
            "time_elapsed": 0,
            "points": 2,
            "shooter": rebounder_param,
        }

    monkeypatch.setattr("BackEnd.models.shot_manager.resolve_offensive_rebound_loop", fake_putback)

    result = shot_manager.resolve_shot(roles)

    assert result["result_type"] == "MAKE"
    assert result["shooter"] is rebounder
    assert result["points"] == 2
    assert rebounder.stats["game"]["FGM"] == 1
    assert rebounder.stats["game"]["FGA"] == 1
    assert rebounder.stats["game"]["OREB"] == 1
    assert game.score[game.offense_team.name] == 2


