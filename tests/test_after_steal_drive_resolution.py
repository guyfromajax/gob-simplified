"""Phase 2 after-steal E2E tests (drive resolution path)."""

from types import SimpleNamespace

import pytest

from BackEnd.engine.after_steal_fast_break import resolve_after_steal_fast_break
from BackEnd.engine.after_steal_fast_break_step_emitter import (
    build_after_steal_fast_break_animation_steps,
)
from tests.test_utils import build_mock_game


@pytest.fixture(autouse=True)
def _enable_drive_resolution(monkeypatch):
    monkeypatch.setattr("BackEnd.constants.USE_FB_DRIVE_RESOLUTION_AFTER_STEAL", True)


def _seed_steal(game):
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    stealer = game.offense_team.lineup["PG"]
    stealer.player_id = "home-PG"
    game.game_state["last_stealer"] = stealer
    game.game_state["last_stealer_coords"] = {"x": 55.0, "y": 25.0}
    game.game_state["offensive_state"] = "FAST_BREAK"
    for team in (game.offense_team, game.defense_team):
        for pos, player in team.lineup.items():
            player.player_id = f"{team.name}-{pos}"
            player.coords = {"x": 50.0, "y": 25.0}
            player.record_shot_result = lambda *_a, **_k: None
            player.add_momentum = lambda *_a, **_k: None
    return stealer


def test_neutral_hco_returns_defensive_stop(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "NEUTRAL",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "stopper_id": "away-SF",
            "t_meet_game_seconds": 1.2,
            "t_drive_game_seconds": 1.2,
            "defender_end_coords": {"away-SF": meet},
            "defender_archetypes": {"away-SF": "sprint"},
            "stop_decision": {"action": "HCO"},
        },
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "DEFENSIVE_STOP"
    assert result["fb_drive_resolution"]["outcome"] == "NEUTRAL"
    assert result["next_play_type"] == "HCO"


def test_pos_o_stamps_path_knots_on_turn(monkeypatch):
    meet = {"x": 70, "y": 25}
    shimmy = {"x": 70, "y": 27}
    shot_spot = {"x": 88, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "POS_O",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "bh_path_knots": [
                {"x": 55, "y": 25},
                meet,
                shimmy,
                shot_spot,
            ],
            "shot_spot": shot_spot,
            "t_drive_game_seconds": 2.0,
            "contested": False,
            "defender_end_coords": {},
            "defender_archetypes": {},
        },
    )
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration._resolve_shot_attempt",
        lambda **kwargs: {
            "made": True,
            "d_foul": False,
            "foul_player": None,
            "has_and_one": False,
            "free_throws_remaining": 0,
            "fouled_out_info": {},
            "shot_score": 200,
            "shot_score_pre_defense": 180,
            "shot_defense_score_for_sfx": 0,
            "shot_defense_score_raw": 0,
            "shot_variant": None,
            "shot_variant_extras": {},
            "contest_result": None,
            "contest_margin": None,
            "shot_type": "attack",
            "contested": False,
            "shot_defender": None,
            "shot_defender_id": None,
            "select_and_stamp_shot_micro_kwargs": {
                "shot_type": "attack",
                "shooter_id": "home-PG",
                "shooter_x": 88.0,
                "shooter_y": 25.0,
                "off_lineup": {},
                "def_lineup": {},
                "has_contest": False,
                "contest_result": None,
                "contest_margin": None,
                "shot_defense_score_raw": 0.0,
            },
        },
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "MAKE"
    assert len(result["fb_drive_resolution"]["bh_path_knots"]) == 4


def test_emitter_includes_path_knots_metadata_for_pos_o():
    meet = {"x": 70, "y": 25}
    shot_spot = {"x": 88, "y": 25}
    end_coords = {
        f"home-{pos}": {"x": 60.0, "y": 25.0}
        for pos in ("PG", "SG", "SF", "PF", "C")
    }
    end_coords["home-PG"] = dict(shot_spot)
    for pos in ("PG", "SG", "SF", "PF", "C"):
        end_coords[f"away-{pos}"] = {"x": 50.0, "y": 25.0}

    turn_result = {
        "result_type": "MAKE",
        "shooter_id": "home-PG",
        "ball_handler": SimpleNamespace(player_id="home-PG"),
        "bh_target": shot_spot,
        "t_shooter_game_seconds": 2.0,
        "after_steal_end_coords": end_coords,
        "fb_drive_resolution": {
            "outcome": "POS_O",
            "bh_path_knots": [
                {"x": 55, "y": 25},
                meet,
                {"x": 70, "y": 27},
                shot_spot,
            ],
            "t_drive_game_seconds": 2.0,
        },
        "shot_score_pre_defense": 100,
        "shot_defense_score_for_sfx": 0,
        "shot_type": "attack",
        "shot_variant": None,
    }
    game = build_mock_game()
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    game.turns = [{"final_coords": {pid: {"x": 50.0, "y": 25.0} for pid in end_coords}}]
    for pos, player in game.home_team.lineup.items():
        player.player_id = f"home-{pos}"
    for pos, player in game.away_team.lineup.items():
        player.player_id = f"away-{pos}"

    steps = build_after_steal_fast_break_animation_steps(turn_result, game)
    assert steps is not None
    meta = steps[0]["start"]["advance_trigger"]["metadata"]
    assert "path_knots" in meta
    assert len(meta["path_knots"]) == 4
