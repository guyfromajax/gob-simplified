"""Phase 4 Rim Runner + Triangle drive resolution tests."""

from types import SimpleNamespace

import pytest

from BackEnd.constants.fast_break_play_types import RIM_RUNNER, TRIANGLE
from BackEnd.engine.rim_runner_drive_integration import (
    apply_triangle_unified_contest,
    resolve_attack_drive_finisher_turn,
)
from BackEnd.engine.rim_runner_step_emitter import _build_finisher_drive_resolution_steps
from tests.test_utils import build_mock_game


@pytest.fixture(autouse=True)
def _enable_rr_triangle_drive_resolution(monkeypatch):
    monkeypatch.setattr("BackEnd.constants.USE_FB_DRIVE_RESOLUTION_RR", True)
    monkeypatch.setattr("BackEnd.constants.USE_FB_DRIVE_RESOLUTION_TRIANGLE", True)


def _seed_rr_finisher(game):
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    rr = game.home_team.lineup["PF"]
    bh = game.home_team.lineup["PG"]
    for team in (game.offense_team, game.defense_team):
        for pos, player in team.lineup.items():
            player.player_id = f"{team.name}-{pos}"
            player.coords = {"x": 50.0, "y": 25.0}
            player.record_shot_result = lambda *_a, **_k: None
            player.add_momentum = lambda *_a, **_k: None
    fb_animations = []
    for team in (game.home_team, game.away_team):
        for pos in ("PG", "SG", "SF", "PF", "C"):
            fb_animations.append(
                {
                    "playerId": f"{team.name}-{pos}",
                    "end": {"x": 60.0, "y": 25.0},
                }
            )
    fb_roles = {
        "ball_handler": bh,
        "shooter": rr,
        "rim_runner_burst_phase": {"rr_id": rr.player_id},
        "fast_break_play": RIM_RUNNER,
    }
    return rr, bh, fb_roles, fb_animations


def test_rr_finisher_neutral_hco(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration.resolve_fb_drive_step",
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
    rr, bh, fb_roles, fb_animations = _seed_rr_finisher(game)
    result = resolve_attack_drive_finisher_turn(
        game=game,
        shooter=rr,
        shot_spot={"x": 88, "y": 25},
        fb_roles=fb_roles,
        fb_animations=fb_animations,
        fb_play_key=RIM_RUNNER,
        off_team=game.offense_team,
        def_team=game.defense_team,
        off_lineup=game.offense_team.lineup,
        def_lineup=game.defense_team.lineup,
        is_away_offense=False,
        ball_handler=bh,
        pass_attempted=True,
        fb_open=True,
    )

    assert result is not None
    assert result["result_type"] == "DEFENSIVE_STOP"
    assert result["fb_drive_resolution"]["outcome"] == "NEUTRAL"
    assert result["next_play_type"] == "HCO"


def test_triangle_bh_drive_stamps_fb_drive_resolution(monkeypatch):
    meet = {"x": 70, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "POS_O",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "bh_path_knots": [
                {"x": 55, "y": 25},
                meet,
                {"x": 70, "y": 27},
                {"x": 88, "y": 25},
            ],
            "t_drive_game_seconds": 2.0,
            "contested": False,
            "defender_end_coords": {},
            "defender_archetypes": {},
        },
    )
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration._resolve_shot_attempt",
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
                "shooter_id": "Lancaster-PG",
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
    bh = game.home_team.lineup["PG"]
    bh.player_id = "Lancaster-PG"
    bh.coords = {"x": 55, "y": 25}
    fb_animations = [{"playerId": "Lancaster-PG", "end": {"x": 55, "y": 25}}]
    fb_roles = {"ball_handler": bh, "rim_runner_burst_phase": {"rr_id": "Lancaster-PF"}}

    result = resolve_attack_drive_finisher_turn(
        game=game,
        shooter=bh,
        shot_spot={"x": 70, "y": 25},
        fb_roles=fb_roles,
        fb_animations=fb_animations,
        fb_play_key=TRIANGLE,
        off_team=game.home_team,
        def_team=game.away_team,
        off_lineup=game.home_team.lineup,
        def_lineup=game.away_team.lineup,
        is_away_offense=False,
        ball_handler=bh,
        pass_attempted=False,
        fb_open=True,
        extra_turn_fields={"triangle_branch": "triangle_bh_drive"},
    )

    assert result is not None
    assert result["result_type"] == "MAKE"
    assert len(result["fb_drive_resolution"]["bh_path_knots"]) == 4


def test_triangle_unified_contest_replaces_six_grid(monkeypatch):
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration.pick_nearest_contesting_defender",
        lambda *_a, **_k: (True, "Bentley-Truman-PG"),
    )
    game = build_mock_game()
    def_lineup = game.away_team.lineup
    for pos, player in def_lineup.items():
        player.player_id = f"Bentley-Truman-{pos}"
        player.coords = {"x": 80.0, "y": 25.0}

    defender, count = apply_triangle_unified_contest(
        def_lineup=def_lineup,
        shot_spot={"x": 85, "y": 25},
        is_away_offense=False,
        branch="triangle_corner_three",
    )

    assert count == 1
    assert defender is not None


def test_emitter_finisher_drive_includes_path_knots_metadata():
    meet = {"x": 70, "y": 25}
    shot_spot = {"x": 88, "y": 25}
    end_coords = {
        f"Lancaster-{pos}": {"x": 60.0, "y": 25.0}
        for pos in ("PG", "SG", "SF", "PF", "C")
    }
    end_coords["Lancaster-PF"] = dict(shot_spot)
    for pos in ("PG", "SG", "SF", "PF", "C"):
        end_coords[f"Bentley-Truman-{pos}"] = {"x": 50.0, "y": 25.0}

    start_coords = {pid: {"x": 65.0, "y": 25.0} for pid in end_coords}
    turn_result = {
        "result_type": "MAKE",
        "shooter": SimpleNamespace(player_id="Lancaster-PF"),
        "bh_target": shot_spot,
        "t_shooter_game_seconds": 2.0,
        "rr_end_coords": end_coords,
        "roles": {"rim_runner_burst_phase": {"rr_id": "Lancaster-PF"}},
        "fb_drive_resolution": {
            "outcome": "POS_O",
            "bh_path_knots": [
                {"x": 65, "y": 25},
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

    steps = _build_finisher_drive_resolution_steps(
        turn_result=turn_result,
        game=game,
        start_coords=start_coords,
        off_lineup=game.home_team.lineup,
        def_lineup=game.away_team.lineup,
        is_away_offense=False,
        clock_remaining=600.0,
        shot_clock_remaining=24.0,
        fb_roles=turn_result["roles"],
    )

    assert steps is not None
    drive_step = steps[0]
    meta = drive_step["start"]["advance_trigger"]["metadata"]
    assert meta.get("path_knots") is not None
    assert meta["kind"] == "rim_runner_drive"


def test_rebase_animation_step_next_indices_offsets_next_step_pointers():
    from BackEnd.utils.animation_step_helpers import rebase_animation_step_next_indices

    steps = [
        {"end": {"next": {"kind": "next_step", "index": 1}}},
        {"end": {"next": {"kind": "next_step", "index": 2}}},
        {"end": {"next": {"kind": "end_of_turn"}}},
    ]
    rebase_animation_step_next_indices(steps, 4)
    assert steps[0]["end"]["next"]["index"] == 5
    assert steps[1]["end"]["next"]["index"] == 6
    assert steps[2]["end"]["next"]["kind"] == "end_of_turn"


def test_finisher_meet_step_rebased_next_index_and_motion():
    """Meet step local next=1 must become global base+1; defenders get interrupted coords."""
    from BackEnd.utils.animation_step_helpers import rebase_animation_step_next_indices

    meet = {"x": 70, "y": 25}
    shot_spot = {"x": 88, "y": 25}
    end_coords = {
        f"Lancaster-{pos}": {"x": 60.0, "y": 25.0}
        for pos in ("PG", "SG", "SF", "PF", "C")
    }
    end_coords["Lancaster-PF"] = dict(shot_spot)
    for pos in ("PG", "SG", "SF", "PF", "C"):
        end_coords[f"Bentley-Truman-{pos}"] = {"x": 91.0, "y": 25.0}

    start_coords = {pid: {"x": 65.0, "y": 25.0} for pid in end_coords}
    turn_result = {
        "result_type": "MAKE",
        "shooter": SimpleNamespace(player_id="Lancaster-PF"),
        "meet_coords": meet,
        "bh_target": shot_spot,
        "t_meet_game_seconds": 1.0,
        "t_shooter_game_seconds": 2.0,
        "rr_end_coords": end_coords,
        "roles": {"rim_runner_burst_phase": {"rr_id": "Lancaster-PF"}},
        "fb_drive_resolution": {
            "outcome": "NEUTRAL",
            "stop_decision": {"action": "shoot"},
            "t_meet_game_seconds": 1.0,
            "t_drive_game_seconds": 2.0,
            "defender_archetypes": {"Bentley-Truman-PG": "sprint"},
        },
        "stop_decision_action": "shoot",
        "shot_score_pre_defense": 100,
        "shot_defense_score_for_sfx": 0,
        "shot_type": "attack",
    }

    game = build_mock_game()
    for team in (game.home_team, game.away_team):
        for pos, player in team.lineup.items():
            player.player_id = f"{team.name}-{pos}"
            player.coords = {"x": 50.0, "y": 25.0}

    dr_steps = _build_finisher_drive_resolution_steps(
        turn_result=turn_result,
        game=game,
        start_coords=start_coords,
        off_lineup=game.home_team.lineup,
        def_lineup=game.away_team.lineup,
        is_away_offense=False,
        clock_remaining=600.0,
        shot_clock_remaining=24.0,
        fb_roles=turn_result["roles"],
    )
    assert dr_steps is not None
    base = 4
    rebase_animation_step_next_indices(dr_steps, base)

    meet_step = dr_steps[0]
    assert meet_step["end"]["next"]["index"] == base + 1
    assert meet_step["start"].get("tween_durations")
    def_end = meet_step["end"]["coords"]["Bentley-Truman-PG"]
    assert def_end["x"] < 91.0
