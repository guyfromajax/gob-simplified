import pytest
from unittest.mock import patch
from fastapi import HTTPException
from tests.test_utils import build_mock_game
from BackEnd.engine.phase_resolution import resolve_free_throw_logic
import BackEnd.engine.phase_resolution as phase_resolution_module
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


def test_string_shooter_reference_resolves_to_unique_live_player():
    game, shooter = _setup_game(one_and_one=False)
    game.game_state["shooter"] = shooter.name
    game.game_state["last_ball_handler"] = None

    result = resolve_free_throw_logic(game)

    assert result["shooter"] is shooter
    assert game.game_state["shooter"] is shooter


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
    monkeypatch.setattr("BackEnd.engine.phase_resolution.random.random", lambda: 1.0)
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
    monkeypatch.setattr("BackEnd.engine.phase_resolution.random.random", lambda: 1.0)
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


def test_missed_final_ft_dreb_no_fast_break_while_flag_disabled(monkeypatch):
    """TEMP: _FT_MISS_DREB_FAST_BREAK_ENABLED False → DREB after last FT miss sets HCO, not FAST_BREAK."""
    assert phase_resolution_module._FT_MISS_DREB_FAST_BREAK_ENABLED is False
    game, shooter = _setup_game(one_and_one=False)
    shooter.attributes["FT"] = 1
    shooter.attributes["CH"] = 1
    shooter.attributes["MO"] = 0
    dreb_c = game.defense_team.lineup["C"]

    def fake_determine_rebounder(
        g, bounce_spot=None, exclude_player_ids=None, penalize_player_ids=None, **kwargs
    ):
        return dreb_c, game.defense_team, "DREB"

    monkeypatch.setattr(
        "BackEnd.engine.phase_resolution.random.randint",
        lambda a, b: 100 if (a, b) == (1, 100) else 1,
    )
    monkeypatch.setattr("BackEnd.engine.phase_resolution.random.random", lambda: 1.0)
    monkeypatch.setattr("BackEnd.engine.phase_resolution.determine_rebounder", fake_determine_rebounder)
    with patch.object(Animator, "capture_free_throw_animation", return_value=[]):
        result = resolve_free_throw_logic(game)

    assert result.get("rebound_type") == "DREB"
    assert result.get("next_play_type") == "HCO"
    assert game.game_state["offensive_state"] == "HCO"


def test_missed_final_ft_rebound_uses_ft_updated_player_coords(monkeypatch):
    game, shooter = _setup_game(one_and_one=False)
    shooter.attributes["FT"] = 1
    shooter.attributes["CH"] = 1
    shooter.attributes["MO"] = 0

    offense_pg = game.offense_team.lineup["PG"]
    defense_c = game.defense_team.lineup["C"]
    offense_pg.player_id = "mock_ft_off_pg"
    defense_c.player_id = "mock_ft_def_c"
    offense_pg_id = offense_pg.player_id
    defense_c_id = defense_c.player_id

    # Ensure starting coords are different from animation endpoints.
    offense_pg.coords = {"x": 15, "y": 10}
    defense_c.coords = {"x": 90, "y": 40}
    expected_pg_end = {"x": 74, "y": 25}
    expected_c_end = {"x": 89, "y": 19}

    ft_anims = [
        {
            "playerId": offense_pg_id,
            "end": expected_pg_end,
            "movement": [],
        },
        {
            "playerId": defense_c_id,
            "end": expected_c_end,
            "movement": [],
        },
        {
            "playerId": "ball",
            "end": {"x": 91, "y": 25},
            "movement": [],
        },
    ]

    def fake_determine_rebounder(
        g, bounce_spot=None, exclude_player_ids=None, penalize_player_ids=None, **kwargs
    ):
        # Critical assertion: coords are already synced from FT animation endpoints.
        assert offense_pg.coords == expected_pg_end
        assert defense_c.coords == expected_c_end
        return defense_c, game.defense_team, "DREB"

    monkeypatch.setattr(
        "BackEnd.engine.phase_resolution.random.randint",
        lambda a, b: 100 if (a, b) == (1, 100) else 1,
    )
    monkeypatch.setattr("BackEnd.engine.phase_resolution.random.random", lambda: 1.0)
    monkeypatch.setattr("BackEnd.engine.phase_resolution.determine_rebounder", fake_determine_rebounder)
    monkeypatch.setattr(Animator, "capture_free_throw_animation", lambda *args, **kwargs: ft_anims)

    result = resolve_free_throw_logic(game)
    assert result.get("rebound_type") == "DREB"


def test_missed_final_ft_away_offense_rebound_uses_court_absolute_coords(monkeypatch):
    """Away FT: apply_coords flips animation finals to runtime-home; rebound math must see absolutes."""
    game, shooter = _setup_game(one_and_one=False)
    game.offense_team = game.away_team
    game.defense_team = game.home_team
    shooter = game.offense_team.lineup["PG"]
    game.game_state["shooter"] = shooter
    game.game_state["last_ball_handler"] = shooter

    shooter.attributes["FT"] = 1
    shooter.attributes["CH"] = 1
    shooter.attributes["MO"] = 0

    offense_pg = game.offense_team.lineup["PG"]
    defense_c = game.defense_team.lineup["C"]
    offense_pg.player_id = "mock_ft_away_off_pg"
    defense_c.player_id = "mock_ft_away_def_c"
    offense_pg_id = offense_pg.player_id
    defense_c_id = defense_c.player_id

    offense_pg.coords = {"x": 15, "y": 10}
    defense_c.coords = {"x": 90, "y": 40}
    # Animator finals (court-absolute); after apply_coords away-offense → runtime-home flip.
    anim_pg = {"x": 26, "y": 25}
    anim_c = {"x": 11, "y": 19}
    expected_runtime_pg = {"x": 100 - anim_pg["x"], "y": anim_pg["y"]}
    expected_runtime_c = {"x": 100 - anim_c["x"], "y": anim_c["y"]}

    ft_anims = [
        {"playerId": offense_pg_id, "end": anim_pg, "movement": []},
        {"playerId": defense_c_id, "end": anim_c, "movement": []},
        {"playerId": "ball", "end": {"x": 9, "y": 25}, "movement": []},
    ]

    def fake_determine_rebounder(
        g, bounce_spot=None, exclude_player_ids=None, penalize_player_ids=None, **kwargs
    ):
        # Mock bypasses shared.determine_rebounder; coords stay runtime-home after apply_coords.
        assert offense_pg.coords == expected_runtime_pg
        assert defense_c.coords == expected_runtime_c
        return defense_c, game.defense_team, "DREB"

    monkeypatch.setattr(
        "BackEnd.engine.phase_resolution.random.randint",
        lambda a, b: 100 if (a, b) == (1, 100) else 1,
    )
    monkeypatch.setattr("BackEnd.engine.phase_resolution.random.random", lambda: 1.0)
    monkeypatch.setattr(
        "BackEnd.engine.phase_resolution.determine_rebounder",
        fake_determine_rebounder,
    )
    monkeypatch.setattr(Animator, "capture_free_throw_animation", lambda *args, **kwargs: ft_anims)

    result = resolve_free_throw_logic(game)
    assert result.get("rebound_type") == "DREB"
    assert offense_pg.coords == expected_runtime_pg
    assert defense_c.coords == expected_runtime_c
