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


def test_rr_finisher_defensive_foul_non_bonus_routes_to_side_inbound(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration.resolve_fb_drive_step",
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
    assert result["result_type"] == "FOUL"
    assert result["next_play_type"] == "SIDE_INBOUND"
    assert game.game_state["free_throws_remaining"] == 0
    assert result["meet_coords"] == meet


def test_rr_finisher_defensive_foul_bonus_routes_to_free_throw(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration.resolve_fb_drive_step",
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
    game.defense_team.team_fouls = 5
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

    assert result["result_type"] == "FOUL"
    assert result["next_play_type"] == "FREE_THROW"
    assert game.game_state["shooter"] is rr
    assert game.game_state["free_throws_remaining"] == 1


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


def test_def_starts_seeded_from_live_coords_not_animation_ends(monkeypatch):
    """Regression: the drive-cutoff race must seed defenders from their LIVE
    positions (player.coords), not their fast-break animation `end` coords.

    Animation ends are get-back destinations near the rim, which teleport
    get-back defenders onto the drive line and credit phantom "Nice stop"
    cutoffs no defender could physically make. The fixture puts live coords at
    x=50 and animation ends at x=60, so seeding correctly reads x=50.
    """
    captured = {}

    def _spy(**kwargs):
        captured["def_starts"] = kwargs.get("def_starts")
        return {
            "outcome": "NEUTRAL",
            "meet_x": 75,
            "meet_y": 25,
            "stopper_id": "Bentley-Truman-SF",
            "t_meet_game_seconds": 1.0,
            "t_drive_game_seconds": 1.0,
            "defender_end_coords": {"Bentley-Truman-SF": {"x": 75, "y": 25}},
            "defender_archetypes": {"Bentley-Truman-SF": "sprint"},
            "stop_decision": {"action": "HCO"},
        }

    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration.resolve_fb_drive_step", _spy
    )

    game = build_mock_game()
    rr, bh, fb_roles, fb_animations = _seed_rr_finisher(game)
    resolve_attack_drive_finisher_turn(
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

    def_starts = captured["def_starts"]
    assert def_starts, "resolve_fb_drive_step should receive def_starts"
    # Live coords are x=50; animation ends are x=60. Seeding must read live.
    for coord in def_starts.values():
        assert coord["x"] == pytest.approx(50.0)
        assert coord["x"] != pytest.approx(60.0)


def _bh_start_spy(captured):
    def _spy(**kwargs):
        captured["bh_start"] = kwargs.get("bh_start")
        return {
            "outcome": "NEUTRAL",
            "meet_x": None,
            "meet_y": None,
            "stopper_id": None,
            "t_meet_game_seconds": 1.0,
            "t_drive_game_seconds": 1.0,
            "defender_end_coords": {},
            "defender_archetypes": {},
            "stop_decision": {"action": "HCO"},
        }

    return _spy


def test_rr_bh_start_seeded_from_rr_to_not_animation_packet(monkeypatch):
    """Regression: the RR drive-onset must be seeded from the emitter's
    lane-pass catch target (``rim_runner_burst_phase.rr_to``), not the legacy
    animation packet `end` (x=60) or the RR's live end-of-DREB coords (x=50).
    """
    captured = {}
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration.resolve_fb_drive_step",
        _bh_start_spy(captured),
    )

    game = build_mock_game()
    rr, bh, fb_roles, fb_animations = _seed_rr_finisher(game)
    fb_roles["rim_runner_burst_phase"]["rr_to"] = {
        "x": 33.0,
        "y": 37.0,
        "game_seconds": 0.35,
        "movement_archetype": "burst",
    }

    resolve_attack_drive_finisher_turn(
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

    bh_start = captured["bh_start"]
    assert bh_start == {"x": 33.0, "y": 37.0}
    assert bh_start["x"] != pytest.approx(60.0)  # not the animation packet end
    assert bh_start["x"] != pytest.approx(50.0)  # not the live end-of-DREB coord


def test_triangle_bh_drive_bh_start_seeded_from_ball_handler_to(monkeypatch):
    """Regression: the triangle_bh_drive shooter drives from his triangle setup
    spot (``triangle_setup_phase.ball_handler_to``), which is what the emitter
    moves him to before the drive step \u2014 not the animation packet end.
    """
    captured = {}
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration.resolve_fb_drive_step",
        _bh_start_spy(captured),
    )

    game = build_mock_game()
    rr, bh, fb_roles, fb_animations = _seed_rr_finisher(game)
    # Triangle path: no rim_runner_burst_phase.rr_to; drive-onset comes from the
    # triangle setup payload's ball_handler_to.
    fb_roles["rim_runner_burst_phase"] = {}
    fb_roles["triangle_branch"] = "triangle_bh_drive"
    fb_roles["triangle_setup_phase"] = {
        "ball_handler_to": {"x": 41.0, "y": 18.0},
    }

    resolve_attack_drive_finisher_turn(
        game=game,
        shooter=bh,
        shot_spot={"x": 88, "y": 25},
        fb_roles=fb_roles,
        fb_animations=fb_animations,
        fb_play_key=TRIANGLE,
        off_team=game.offense_team,
        def_team=game.defense_team,
        off_lineup=game.offense_team.lineup,
        def_lineup=game.defense_team.lineup,
        is_away_offense=False,
        ball_handler=bh,
        pass_attempted=True,
        fb_open=True,
    )

    bh_start = captured["bh_start"]
    assert bh_start == {"x": 41.0, "y": 18.0}
    assert bh_start["x"] != pytest.approx(60.0)  # not the animation packet end


def test_resolver_ignores_animation_packet_for_logic(monkeypatch):
    """Phase 3: the drive resolver must not read the legacy animation packet for
    any logic decision. With an EMPTY ``fb_animations`` the turn still resolves
    (all geometry comes from live/backend coords), and the packet is passed
    through only as the render artifact ``turn_result["animations"]``.
    """
    captured = {}
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration.resolve_fb_drive_step",
        _bh_start_spy(captured),
    )

    game = build_mock_game()
    rr, bh, fb_roles, _ = _seed_rr_finisher(game)
    fb_roles["rim_runner_burst_phase"]["rr_to"] = {"x": 33.0, "y": 37.0}

    turn = resolve_attack_drive_finisher_turn(
        game=game,
        shooter=rr,
        shot_spot={"x": 88, "y": 25},
        fb_roles=fb_roles,
        fb_animations=[],  # empty legacy packet
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

    assert turn is not None
    assert turn.get("result_type")  # resolved despite an empty animation packet
    assert turn["animations"] == []  # packet is a render-only passthrough
    # Drive-onset still came from live/backend geometry, not the packet.
    assert captured["bh_start"] == {"x": 33.0, "y": 37.0}


@pytest.mark.parametrize(
    "is_away_offense, x_lo, x_hi",
    [
        (False, 87.0, 89.0),  # home attacks x=91 rim → 91-(2..4)
        (True, 11.0, 13.0),   # away attacks x=9 rim → 9+(2..4)
    ],
)
def test_rr_shot_spot_is_rim_relative_not_animator_packet(is_away_offense, x_lo, x_hi):
    """Phase 2: the Rim Runner shot spot is rim-relative geometry
    (``_compute_bh_target``) rather than the animator-written ``_bh_final_x/_y``.

    This is the exact helper ``resolve_rim_runner_fast_break`` now stamps into
    ``roles["shot_spot"]`` at all three RR shot seams. Guards the "shot from the
    complete other side of the court" regression class: the spot must sit within
    2–4 grid of the attacking rim, never in the backcourt.
    """
    from BackEnd.engine.rim_runner_fast_break import _compute_bh_target as rr_bh_target

    for _ in range(50):
        spot = rr_bh_target(is_away_offense)
        assert x_lo <= spot["x"] <= x_hi
        assert 19.0 <= spot["y"] <= 31.0


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
                "shooter_player": kwargs["shooter"],
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


def _made_shot_stub(shooter):
    return {
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
            "shooter_player": shooter,
            "shot_type": "attack",
            "shooter_id": shooter.player_id,
            "shooter_x": 88.0,
            "shooter_y": 25.0,
            "off_lineup": {},
            "def_lineup": {},
            "has_contest": False,
            "contest_result": None,
            "contest_margin": None,
            "shot_defense_score_raw": 0.0,
        },
    }


def test_pos_o_make_resets_offensive_state_off_fast_break(monkeypatch):
    """Regression: a made POS_O rim finish must clear offensive_state so the
    flipped possession after the baseline inbound doesn't loop into another FB."""
    meet = {"x": 70, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "POS_O",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "bh_path_knots": [{"x": 55, "y": 25}, meet, {"x": 88, "y": 25}],
            "t_drive_game_seconds": 2.0,
            "contested": False,
            "defender_end_coords": {},
            "defender_archetypes": {},
        },
    )
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration._resolve_shot_attempt",
        lambda **kwargs: _made_shot_stub(kwargs["shooter"]),
    )

    game = build_mock_game()
    game.game_state["offensive_state"] = "FAST_BREAK"
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

    assert result["result_type"] == "MAKE"
    assert game.game_state["offensive_state"] != "FAST_BREAK"
    assert result.get("next_defensive_setup")


def test_neutral_shoot_make_resets_offensive_state_off_fast_break(monkeypatch):
    """Regression: a made shot out of a NEUTRAL meet must also clear
    offensive_state off FAST_BREAK (meet-path make branch)."""
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
            "stop_decision": {"action": "shoot", "shot_type": "inside"},
        },
    )

    game = build_mock_game()
    game.game_state["offensive_state"] = "FAST_BREAK"
    rr, bh, fb_roles, fb_animations = _seed_rr_finisher(game)
    monkeypatch.setattr(
        "BackEnd.engine.rim_runner_drive_integration._resolve_shot_attempt",
        lambda **kwargs: _made_shot_stub(kwargs["shooter"]),
    )

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

    assert result["result_type"] == "MAKE"
    assert game.game_state["offensive_state"] != "FAST_BREAK"
    assert result.get("next_defensive_setup")


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


def test_finisher_rim_finish_spreads_offball_instead_of_crashing():
    """RR/Triangle rim finishes now author the coordinated transition spread
    (leads → mid-post, trailers → arc, defenders → matchups/help) instead of the
    old blanket crash that parked the whole cast on the rim."""
    from BackEnd.constants import HCO_STRING_SPOTS

    shot_spot = {"x": 88.0, "y": 25.0}
    # Bunched near midcourt; offense leads (PG/SG) are closest to the basket,
    # trailers (SF/C) lag; the shooter (PF) is the ball handler.
    start_coords = {
        "Lancaster-PF": {"x": 72.0, "y": 25.0},
        "Lancaster-PG": {"x": 70.0, "y": 26.0},
        "Lancaster-SG": {"x": 68.0, "y": 24.0},
        "Lancaster-SF": {"x": 40.0, "y": 20.0},
        "Lancaster-C": {"x": 38.0, "y": 35.0},
        "Bentley-Truman-PG": {"x": 69.0, "y": 25.0},
        "Bentley-Truman-SG": {"x": 66.0, "y": 28.0},
        "Bentley-Truman-SF": {"x": 60.0, "y": 22.0},
        "Bentley-Truman-PF": {"x": 45.0, "y": 20.0},
        "Bentley-Truman-C": {"x": 43.0, "y": 35.0},
    }
    end_coords = {pid: dict(c) for pid, c in start_coords.items()}
    end_coords["Lancaster-PF"] = dict(shot_spot)

    turn_result = {
        "result_type": "MAKE",
        "shooter": SimpleNamespace(player_id="Lancaster-PF"),
        "bh_target": shot_spot,
        "t_shooter_game_seconds": 2.0,
        "rr_end_coords": end_coords,
        "roles": {"rim_runner_burst_phase": {"rr_id": "Lancaster-PF"}},
        "fb_drive_resolution": {
            "outcome": "NO_MEET",
            "stopper_id": "Bentley-Truman-PG",
            "meet_x": 78.0,
            "meet_y": 25.0,
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
    dest = steps[0]["start"]["destination"]

    basket = {"x": 91.0, "y": 25.0}
    offball_off = ["Lancaster-PG", "Lancaster-SG", "Lancaster-SF", "Lancaster-C"]
    # No longer a blanket crash: not every off-ball player parks on the rim.
    assert not all(dest[pid] == basket for pid in offball_off)

    midpost_x = float(HCO_STRING_SPOTS["upper midPost"]["x"])
    # Leads (closest to the basket) pull back to the mid-post on distinct tiers.
    assert dest["Lancaster-PG"]["x"] == midpost_x
    assert dest["Lancaster-SG"]["x"] == midpost_x
    assert dest["Lancaster-PG"]["y"] != dest["Lancaster-SG"]["y"]
    # Trailers spread to the 3-point arc downcourt (home arc x >= 64).
    assert dest["Lancaster-SF"]["x"] >= 64
    assert dest["Lancaster-C"]["x"] >= 64
    # Defenders take up coordinated spots, not all crashing the rim.
    def_dests = {
        (dest[f"Bentley-Truman-{p}"]["x"], dest[f"Bentley-Truman-{p}"]["y"])
        for p in ("PG", "SG", "SF", "PF", "C")
    }
    assert len(def_dests) >= 3


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


def test_finisher_neutral_meet_reaches_meet_and_hands_off_rendered_coords():
    """Regression: a stale/short ``t_meet`` must not clamp the shooter short of
    the meet and then jet him on the shot step. The meet step is floored to his
    real traversal so he actually reaches the meet, and the shot step starts
    from the meet step's RENDERED end coords (not the stale semantic coords)."""
    meet = {"x": 9.0, "y": 15.0}
    shooter_start = {"x": 13.0, "y": 40.0}  # ~25 grid units from the meet
    shooter_id = "Lancaster-PF"

    start_coords = {
        f"Lancaster-{pos}": {"x": 13.0, "y": 40.0}
        for pos in ("PG", "SG", "SF", "PF", "C")
    }
    for pos in ("PG", "SG", "SF", "PF", "C"):
        start_coords[f"Bentley-Truman-{pos}"] = {"x": 20.0, "y": 25.0}

    # Deliberately stale rr_end_coords for the shooter (far from the meet) to
    # prove the shot step reads the meet step's rendered coords, not these.
    end_coords = {pid: dict(c) for pid, c in start_coords.items()}
    end_coords[shooter_id] = {"x": 88.0, "y": 25.0}

    turn_result = {
        "result_type": "MISS",
        "shooter": SimpleNamespace(player_id=shooter_id),
        "meet_coords": meet,
        "bh_target": dict(meet),  # NEUTRAL shoot: shot fires from the meet
        "t_meet_game_seconds": 0.1,  # stale/too-short — would clamp on old code
        "t_shooter_game_seconds": 0.1,
        "rr_end_coords": end_coords,
        "roles": {"rim_runner_burst_phase": {"rr_id": shooter_id}},
        "fb_drive_resolution": {
            "outcome": "NEUTRAL",
            "stop_decision": {"action": "shoot"},
            "stopper_id": "Bentley-Truman-PG",
            "t_meet_game_seconds": 0.1,
            "t_drive_game_seconds": 0.1,
            "defender_archetypes": {},
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
            player.coords = {"x": 20.0, "y": 25.0}

    steps = _build_finisher_drive_resolution_steps(
        turn_result=turn_result,
        game=game,
        start_coords=start_coords,
        off_lineup=game.home_team.lineup,
        def_lineup=game.away_team.lineup,
        is_away_offense=True,
        clock_remaining=600.0,
        shot_clock_remaining=24.0,
        fb_roles=turn_result["roles"],
    )

    assert steps is not None
    meet_step = steps[0]
    assert meet_step["start"]["advance_trigger"]["metadata"]["kind"] == "rim_runner_meet"

    # Fix 1/2: meet step is floored to the shooter's real traversal, so he
    # actually arrives at the meet instead of being clamped ~1 unit short.
    meet_end = meet_step["end"]["coords"][shooter_id]
    assert meet_end["x"] == pytest.approx(meet["x"], abs=0.5)
    assert meet_end["y"] == pytest.approx(meet["y"], abs=0.5)
    assert meet_step["end"]["time_elapsed"] > 1.0  # floored up from 0.1

    # Fix (carry-over): the shot step starts from the meet step's RENDERED end
    # coords, not the stale semantic rr_end_coords ((88, 25)).
    drive_step = next(
        s
        for s in steps
        if (s["start"].get("advance_trigger") or {}).get("metadata", {}).get("kind")
        == "rim_runner_drive"
    )
    shot_start = drive_step["start"]["coords"][shooter_id]
    assert shot_start["x"] == pytest.approx(meet_end["x"], abs=1e-6)
    assert shot_start["y"] == pytest.approx(meet_end["y"], abs=1e-6)
    assert shot_start["x"] != pytest.approx(88.0, abs=1.0)


def test_finisher_drive_steps_skip_blocking_fast_break_announcement():
    """Phase 4 RR/Triangle finisher must not stamp a second blocking FB callout."""
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
        "meet_coords": meet,
        "bh_target": shot_spot,
        "t_meet_game_seconds": 1.0,
        "t_shooter_game_seconds": 2.0,
        "rr_end_coords": end_coords,
        "roles": {"rim_runner_burst_phase": {"rr_id": "Lancaster-PF"}},
        "fb_drive_resolution": {
            "outcome": "NEUTRAL",
            "stop_decision": {"action": "shoot"},
            "stopper_id": "Bentley-Truman-PG",
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
    drive_meet_steps = [
        step
        for step in steps
        if (step["start"].get("advance_trigger") or {}).get("metadata", {}).get("kind")
        in ("rim_runner_drive", "rim_runner_meet")
    ]
    assert drive_meet_steps, "expected finisher drive/meet steps"
    for step in drive_meet_steps:
        ann = step["start"].get("announcement")
        assert ann is None or ann.get("text") != "Fast Break!"


def test_finisher_pace_uses_standard_for_driver_and_cutoff_defenders():
    from BackEnd.engine.after_steal_fast_break_step_emitter import _build_drive_step

    start_coords = {
        "Lancaster-PF": {"x": 65.0, "y": 25.0},
        "Lancaster-PG": {"x": 60.0, "y": 25.0},
        "Bentley-Truman-PG": {"x": 70.0, "y": 25.0},
    }
    end_coords = {pid: dict(coord) for pid, coord in start_coords.items()}
    end_coords["Lancaster-PF"] = {"x": 88.0, "y": 25.0}

    game = build_mock_game()
    for team in (game.home_team, game.away_team):
        for pos, player in team.lineup.items():
            player.player_id = f"{team.name}-{pos}"
            player.coords = {"x": 50.0, "y": 25.0}

    step = _build_drive_step(
        start_coords=start_coords,
        end_coords=end_coords,
        stealer_id="Lancaster-PF",
        bh_target={"x": 88.0, "y": 25.0},
        is_away_offense=False,
        clock_remaining=600.0,
        shot_clock_remaining=24.0,
        t_game_seconds=1.0,
        next_step_index=1,
        off_lineup=game.home_team.lineup,
        def_lineup=game.away_team.lineup,
        finisher_pace=True,
        stamp_start_announcement=False,
        fb_drive={"stopper_id": "Bentley-Truman-PG"},
    )

    archetypes = step["start"]["archetype"]
    assert archetypes["Lancaster-PF"] == "standard"
    assert archetypes["Bentley-Truman-PG"] == "standard"
    assert archetypes["Lancaster-PG"] == "sprint"


def test_reachable_defender_ends_clamps_far_defender_for_rebound_geo():
    """A defender who can't physically get back must not be collapsed onto the
    rim — otherwise he can win the board / be picked as contester from a spot he
    never reached (the far-rebounder + closeout-jet bug)."""
    from BackEnd.engine.cutoff_resolution import POSITIONS
    from BackEnd.engine.fb_drive_resolution import (
        _build_defender_ends_at_basket,
        _reachable_defender_ends,
    )
    from BackEnd.utils.animation_step_helpers import (
        _ag_grid_per_game_sec,
        _euclid,
    )

    pos_near, pos_far = POSITIONS[0], POSITIONS[1]
    near = SimpleNamespace(player_id="d_near", attributes={"AG": 50})
    far = SimpleNamespace(player_id="d_far", attributes={"AG": 50})
    def_lineup = {pos_near: near, pos_far: far}
    def_starts = {pos_near: {"x": 88.0, "y": 25.0}, pos_far: {"x": 18.0, "y": 25.0}}

    ends, arch = _build_defender_ends_at_basket(
        def_lineup, def_starts, is_away_offense=False,
    )
    basket = dict(ends["d_far"])
    # Baseline bug: both defenders collapsed onto the rim.
    assert _euclid(def_starts[pos_far], basket) > 30.0

    time_budget = 1.0
    clamped = _reachable_defender_ends(
        ends,
        def_lineup=def_lineup,
        def_starts=def_starts,
        archetypes=arch,
        time_budget=time_budget,
    )

    far_rate = _ag_grid_per_game_sec(far, arch["d_far"])
    moved = _euclid(def_starts[pos_far], clamped["d_far"])
    # Far defender only covers what his rate allows in the drive window …
    assert moved <= far_rate * time_budget + 1e-6
    # … so he is NOT sitting under the rim in the selection geometry.
    assert _euclid(clamped["d_far"], basket) > 1.0
    # Near defender is within reach and still lands at the rim.
    assert _euclid(clamped["d_near"], ends["d_near"]) < 1e-6
