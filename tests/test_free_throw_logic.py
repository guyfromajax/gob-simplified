import pytest
from fastapi import HTTPException
from tests.test_utils import build_mock_game
from BackEnd.engine.phase_resolution import resolve_free_throw_logic
from BackEnd.models.animator import Animator


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
    # ensure every FT is made by setting high attributes and controlling random roll
    shooter.attributes["FT"] = 100
    shooter.attributes["CH"] = 100
    shooter.attributes["MO"] = 10
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


def test_missing_shooter_returns_400():
    game = build_mock_game()
    game.game_state.update({
        "offensive_state": "FREE_THROW",
        "free_throws_remaining": 1,
        "shooter": None,
        "last_ball_handler": None,
    })

    with pytest.raises(HTTPException) as excinfo:
        resolve_free_throw_logic(game)

    assert excinfo.value.status_code == 400


def test_free_throw_animation_empty_offense_lineup():
    game = build_mock_game()
    shooter = game.offense_team.lineup["PG"]
    game.offense_team.lineup = {}
    animator = Animator(game)
    packet = animator.capture_free_throw_animation(
        game,
        shooter,
        attempts=["MAKE"],
        offense_is_home=True,
    )
    assert packet == []


def test_two_shot_final_make_flips_possession():
    game, shooter = _setup_game(one_and_one=False)
    game.game_state["free_throws_remaining"] = 2

    first = resolve_free_throw_logic(game)
    assert first["possession_flips"] is False
    assert game.game_state["free_throws_remaining"] == 1

    game.game_state["shooter"] = shooter
    second = resolve_free_throw_logic(game)
    assert second["possession_flips"] is True
    game.turn_manager.update_clock_and_possession(second)
    assert game.offense_team == game.away_team


def test_and_one_make_results_in_baseline_inbound():
    game, _ = _setup_game(one_and_one=False)
    result = resolve_free_throw_logic(game)
    assert result["possession_flips"] is True
    game.turn_manager.update_clock_and_possession(result)
    assert game.offense_team == game.away_team


def test_and_one_miss_results_in_rebound(monkeypatch):
    game, shooter = _setup_game(one_and_one=False)
    # Force a miss by setting low attributes and high roll
    shooter.attributes["FT"] = 1
    shooter.attributes["CH"] = 1
    shooter.attributes["MO"] = 0
    monkeypatch.setattr("BackEnd.engine.phase_resolution.random.randint", lambda a, b: 100 if a == 1 and b == 100 else 1)
    monkeypatch.setattr("BackEnd.engine.phase_resolution.random.random", lambda: 0.0)
    monkeypatch.setattr("BackEnd.engine.phase_resolution.choose_rebounder", lambda r, s: "C")
    result = resolve_free_throw_logic(game)
    assert result["possession_flips"] is True
    assert game.game_state["last_rebounder"] is game.defense_team.lineup["C"]


def test_one_and_one_make_unlocks_second_shot():
    game, _ = _setup_game(one_and_one=True)
    result = resolve_free_throw_logic(game)
    assert result["possession_flips"] is False
    assert game.game_state["free_throws_remaining"] == 1
    assert game.game_state["one_and_one"] is False


def test_one_and_one_miss_ends_possession(monkeypatch):
    game, shooter = _setup_game(one_and_one=True)
    # Force a miss by setting low attributes and high roll
    shooter.attributes["FT"] = 1
    shooter.attributes["CH"] = 1
    shooter.attributes["MO"] = 0
    monkeypatch.setattr("BackEnd.engine.phase_resolution.random.randint", lambda a, b: 100 if a == 1 and b == 100 else 1)
    monkeypatch.setattr("BackEnd.engine.phase_resolution.random.random", lambda: 0.0)
    monkeypatch.setattr("BackEnd.engine.phase_resolution.choose_rebounder", lambda r, s: "C")
    result = resolve_free_throw_logic(game)
    assert result["possession_flips"] is True
    assert game.game_state["free_throws_remaining"] <= 0
    assert game.game_state["one_and_one"] is False


def test_technical_free_throw_retains_possession():
    game, _ = _setup_game(one_and_one=False)
    game.game_state["no_lane"] = True
    result = resolve_free_throw_logic(game)
    assert result["possession_flips"] is False
    game.turn_manager.update_clock_and_possession(result)
    assert game.offense_team == game.home_team
