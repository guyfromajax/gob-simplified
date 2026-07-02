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
