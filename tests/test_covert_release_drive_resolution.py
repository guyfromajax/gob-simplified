"""Phase 3 Covert Release E2E tests (drive resolution path)."""

from types import SimpleNamespace

import pytest

from BackEnd.constants.fast_break_play_types import COVERT_RELEASE
from BackEnd.engine.covert_release_drive_integration import (
    resolve_covert_release_fast_break,
)
from BackEnd.engine.covert_release_step_emitter import (
    build_covert_release_animation_steps,
)
from BackEnd.engine.phase_resolution import resolve_fast_break_logic
from tests.test_utils import build_mock_game


@pytest.fixture(autouse=True)
def _enable_cr_drive_resolution(monkeypatch):
    monkeypatch.setattr("BackEnd.constants.USE_FB_DRIVE_RESOLUTION_CR", True)


def _seed_cr(game):
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    rebounder = game.home_team.lineup["C"]
    release = game.home_team.lineup["SG"]
    game.game_state["last_rebound"] = "DREB"
    game.game_state["last_rebounder"] = rebounder
    game.game_state["last_release_player"] = release
    game.game_state["offensive_state"] = "FAST_BREAK"
    game.game_state["pending_dreb_fb_play_key"] = COVERT_RELEASE
    for team in (game.offense_team, game.defense_team):
        for pos, player in team.lineup.items():
            player.player_id = f"{team.name}-{pos}"
            player.coords = {"x": 50.0, "y": 25.0}
            player.record_shot_result = lambda *_a, **_k: None
            player.add_momentum = lambda *_a, **_k: None
    game.turns = [
        {
            "offense_getback": ["Bentley-Truman-PG", "Bentley-Truman-SF"],
            "offense_getback_coords": {
                "Bentley-Truman-PG": {"x": 60.0, "y": 20.0},
                "Bentley-Truman-SF": {"x": 62.0, "y": 30.0},
            },
            "defense_release_coords": {
                "Lancaster-SG": {"x": 45.0, "y": 25.0},
            },
        }
    ]
    return release


def test_neutral_hco_returns_defensive_stop(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.covert_release_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "NEUTRAL",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "stopper_id": "Bentley-Truman-SF",
            "t_meet_game_seconds": 1.2,
            "t_drive_game_seconds": 1.2,
            "defender_end_coords": {"Bentley-Truman-SF": meet},
            "defender_archetypes": {"Bentley-Truman-SF": "sprint"},
            "stop_decision": {"action": "HCO"},
        },
    )

    game = build_mock_game()
    _seed_cr(game)
    result = resolve_covert_release_fast_break(game)

    assert result["result_type"] == "DEFENSIVE_STOP"
    assert result["fb_drive_resolution"]["outcome"] == "NEUTRAL"
    assert result["next_play_type"] == "HCO"
    assert result["roles"]["outlet_passer"] == "Lancaster-C"
    assert result["roles"]["outlet_receiver"] == "Lancaster-SG"


def test_phase_resolution_short_circuits_cr(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.covert_release_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "NEUTRAL",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "stopper_id": "Bentley-Truman-SF",
            "t_meet_game_seconds": 1.0,
            "t_drive_game_seconds": 1.0,
            "defender_end_coords": {"Bentley-Truman-SF": meet},
            "defender_archetypes": {"Bentley-Truman-SF": "sprint"},
            "stop_decision": {"action": "HCO"},
        },
    )

    game = build_mock_game()
    _seed_cr(game)
    result = resolve_fast_break_logic(game)

    assert result["result_type"] == "DEFENSIVE_STOP"
    assert result.get("fb_drive_resolution") is not None
    assert result.get("animation_steps") is not None


def test_emitter_includes_path_knots_metadata_for_pos_o():
    meet = {"x": 70, "y": 25}
    shot_spot = {"x": 88, "y": 25}
    end_coords = {
        f"Lancaster-{pos}": {"x": 60.0, "y": 25.0}
        for pos in ("PG", "SG", "SF", "PF", "C")
    }
    end_coords["Lancaster-SG"] = dict(shot_spot)
    for pos in ("PG", "SG", "SF", "PF", "C"):
        end_coords[f"Bentley-Truman-{pos}"] = {"x": 50.0, "y": 25.0}

    turn_result = {
        "result_type": "MAKE",
        "fast_break_play": COVERT_RELEASE,
        "shooter_id": "Lancaster-SG",
        "ball_handler": SimpleNamespace(player_id="Lancaster-SG"),
        "bh_target": shot_spot,
        "t_shooter_game_seconds": 2.0,
        "cr_end_coords": end_coords,
        "roles": {
            "ball_handler": SimpleNamespace(player_id="Lancaster-SG"),
            "outlet_passer": "Lancaster-C",
            "outlet_receiver": "Lancaster-SG",
            "is_away_offense": False,
        },
        "fb_drive_resolution": {
            "outcome": "POS_O",
            "bh_path_knots": [
                {"x": 45, "y": 25},
                meet,
                {"x": 70, "y": 27},
                shot_spot,
            ],
            "t_drive_game_seconds": 2.0,
        },
        "shot_score_pre_defense": 100,
        "shot_defense_score_for_sfx": 0,
        "shot_type": "attack",
    }

    game = build_mock_game()
    for team in (game.home_team, game.away_team):
        for pos, player in team.lineup.items():
            player.player_id = f"{team.name}-{pos}"
            player.coords = {"x": 50.0, "y": 25.0}

    game.offense_team = game.home_team
    game.defense_team = game.away_team

    steps = build_covert_release_animation_steps(turn_result, game)
    assert steps is not None
    assert len(steps) >= 2
    drive_step = steps[1]
    meta = drive_step["start"]["advance_trigger"]["metadata"]
    assert meta.get("path_knots") is not None
    assert meta["kind"] == "covert_release_drive"


def test_meet_defensive_foul_non_bonus_routes_to_side_inbound(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.covert_release_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "D_FOUL",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "stopper_id": "Bentley-Truman-SF",
            "d8_credited_player_id": "Bentley-Truman-SF",
            "t_meet_game_seconds": 1.0,
            "t_drive_game_seconds": 1.0,
            "defender_end_coords": {"Bentley-Truman-SF": meet},
            "defender_archetypes": {"Bentley-Truman-SF": "sprint"},
        },
    )

    game = build_mock_game()
    _seed_cr(game)
    result = resolve_covert_release_fast_break(game)

    assert result["result_type"] == "FOUL"
    assert result["next_play_type"] == "SIDE_INBOUND"
    assert game.game_state["free_throws_remaining"] == 0
    assert result["meet_coords"] == meet


def test_no_meet_and_one_routes_to_free_throw_not_baseline_inbound(monkeypatch):
    """Regression: and-1 on a CR rim finish must not leave next_play_type=BIP
    (Pattern A would synthesize an extra inbound before the FT turn)."""
    shot_spot = {"x": 88, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.covert_release_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "NO_MEET",
            "stopper_id": "Bentley-Truman-PG",
            "shot_defender_id": "Bentley-Truman-PG",
            "contested": True,
            "t_drive_game_seconds": 1.5,
            "defender_end_coords": {"Bentley-Truman-PG": {"x": 80, "y": 25}},
            "defender_archetypes": {"Bentley-Truman-PG": "sprint"},
        },
    )
    monkeypatch.setattr(
        "BackEnd.engine.covert_release_drive_integration._resolve_shot_attempt",
        lambda **kwargs: {
            "made": True,
            "d_foul": True,
            "has_and_one": True,
            "free_throws_remaining": 1,
            "foul_player": kwargs.get("shot_defender"),
            "shot_score": 100,
            "shot_score_pre_defense": 100,
            "shot_defense_score_for_sfx": 50,
            "shot_variant": "SWISH",
            "shot_variant_extras": {},
            "select_and_stamp_shot_micro_kwargs": {
                "shot_type": "attack",
                "shooter_id": "Lancaster-SG",
                "shooter_x": float(shot_spot["x"]),
                "shooter_y": float(shot_spot["y"]),
                "off_lineup": kwargs.get("game").offense_team.lineup,
                "def_lineup": kwargs.get("game").defense_team.lineup,
                "has_contest": True,
                "contest_result": None,
                "contest_margin": None,
                "shot_defense_score_raw": 50.0,
            },
            "shot_defender_id": "Bentley-Truman-PG",
        },
    )
    monkeypatch.setattr(
        "BackEnd.engine.shot_micro_movements.select_and_stamp_shot_micro",
        lambda turn_result, **kwargs: None,
    )

    game = build_mock_game()
    _seed_cr(game)
    result = resolve_covert_release_fast_break(game)

    assert result["result_type"] == "MAKE"
    assert result["next_play_type"] == "FREE_THROW"
    assert result.get("free_throws_remaining") == 1
    assert result["possession_flips"] is False
