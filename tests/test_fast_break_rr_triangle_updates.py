from types import SimpleNamespace

from BackEnd.engine.rim_runner_fast_break import (
    _resolve_rr_burst_destination,
    _resolve_triangle_setup_payload,
)
from BackEnd.engine.rim_runner_step_emitter import (
    _build_burst_step,
    _build_outlet_pass_step,
    is_lane_pass_to_rr_resolution_turn,
)
from BackEnd.engine.triangle_step_emitter import build_triangle_animation_steps
from BackEnd.utils.shared import calc_ag_segment_seconds


def _player(player_id, x, y, *, ag=50, iq=50, ch=50):
    return SimpleNamespace(
        player_id=player_id,
        coords={"x": x, "y": y},
        attributes={"AG": ag, "IQ": iq, "CH": ch},
    )


def test_rr_burst_destination_targets_home_basket_spot_without_dynamic_base():
    destination, dynamic_base = _resolve_rr_burst_destination(
        rr_x0=20,
        rr_y0=30,
        outlet_receiver_target_x=45,
        dx_burst=10,
        is_away_offense=False,
        most_recent_shot_turn={"ball_bounce_x": 80},
    )

    assert dynamic_base is None
    assert destination == {"x": 87.0, "y": 25.0}


def test_rr_burst_destination_uses_outlet_receiver_target_for_home_midcourt_bounce():
    destination, dynamic_base = _resolve_rr_burst_destination(
        rr_x0=20,
        rr_y0=30,
        outlet_receiver_target_x=45,
        dx_burst=24,
        is_away_offense=False,
        most_recent_shot_turn={"ball_bounce_x": 40},
    )

    assert dynamic_base == 45.0
    assert destination == {"x": 87.0, "y": 25.0}


def test_rr_burst_destination_uses_outlet_receiver_target_for_away_midcourt_bounce():
    destination, dynamic_base = _resolve_rr_burst_destination(
        rr_x0=80,
        rr_y0=20,
        outlet_receiver_target_x=55,
        dx_burst=22,
        is_away_offense=True,
        most_recent_shot_turn={"ball_bounce_x": 60},
    )

    assert dynamic_base == 55.0
    assert destination == {"x": 13.0, "y": 25.0}


def test_triangle_corner_players_use_sprint_not_burst_payload():
    off_lineup = {
        "PG": _player("bh", 45, 30),
        "SG": _player("lower-corner", 50, 10),
        "SF": _player("upper-corner", 52, 40),
        "PF": _player("rr", 35, 34),
        "C": _player("trailer", 25, 25),
    }
    def_lineup = {
        "PG": _player("d1", 70, 25),
        "SG": _player("d2", 72, 20),
        "SF": _player("d3", 74, 30),
        "PF": _player("d4", 76, 12),
        "C": _player("d5", 78, 38),
    }

    payload = _resolve_triangle_setup_payload(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        ball_handler=off_lineup["PG"],
        rim_runner=off_lineup["PF"],
        rebounder=off_lineup["C"],
        is_away_offense=False,
        fb_opp=0,
    )

    assert len(payload["corner_players"]) == 2
    assert {corner["burst"] for corner in payload["corner_players"]} == {False}


def test_calc_ag_segment_seconds_supports_burst_archetype():
    player = _player("p1", 0, 0, ag=50)
    start = {"x": 0, "y": 0}
    end = {"x": 32, "y": 0}

    burst_seconds = calc_ag_segment_seconds(start, end, player, archetype="burst")
    sprint_seconds = calc_ag_segment_seconds(start, end, player, archetype="sprint")

    assert burst_seconds < sprint_seconds
    assert burst_seconds == 1.0


def test_rim_runner_burst_step_uses_fixed_one_second_sprint_advance():
    off_lineup = {
        "PG": _player("bh", 45, 15),
        "PF": _player("rr", 20, 40),
        "C": _player("passer", 35, 25),
    }
    def_lineup = {}
    start_coords = {
        "bh": {"x": 45.0, "y": 15.0},
        "rr": {"x": 20.0, "y": 40.0},
        "passer": {"x": 35.0, "y": 25.0},
    }
    fb_roles = {
        "rim_runner_burst_phase": {
            "rr_id": "rr",
            "outlet_receiver_id": "bh",
            "outlet_passer_id": "passer",
            "rr_to": {"x": 87.0, "y": 25.0, "movement_archetype": "sprint"},
            "receiver_to": {"x": 45.0, "y": 15.0},
            "other_players": [],
        }
    }

    step = _build_burst_step(
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        all_start_coords=start_coords,
        is_away_offense=False,
        clock_remaining_at_start=300,
        shot_clock_remaining_at_start=20,
        next_step_index=1,
    )

    assert step is not None
    assert step["start"]["archetype"]["rr"] == "sprint"
    assert step["start"]["advance_trigger"]["condition"] == "fixed_duration"
    assert step["end"]["time_elapsed"] == 1.0
    assert step["start"]["tween_durations"]["rr"] == step["end"]["time_elapsed"]
    assert step["end"]["coords"]["rr"]["x"] < 87.0


def test_rim_runner_outlet_pass_carries_forward_burst_archetype():
    off_lineup = {
        "PG": _player("bh", 45, 15),
        "PF": _player("rr", 45, 25),
        "C": _player("passer", 35, 25),
    }
    def_lineup = {}
    start_coords = {
        "bh": {"x": 45.0, "y": 15.0},
        "rr": {"x": 45.0, "y": 25.0},
        "passer": {"x": 35.0, "y": 25.0},
    }
    fb_roles = {
        "outlet_score": 999,
        "rim_runner_burst_phase": {
            "rr_id": "rr",
            "outlet_receiver_id": "bh",
            "outlet_passer_id": "passer",
            "rr_to": {"x": 87.0, "y": 25.0, "movement_archetype": "burst"},
            "receiver_to": {"x": 45.0, "y": 15.0},
            "other_players": [],
        }
    }

    step = _build_outlet_pass_step(
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        step_start_coords=start_coords,
        is_away_offense=False,
        clock_remaining_at_start=300,
        shot_clock_remaining_at_start=20,
        next_step_index=2,
    )

    assert step is not None
    assert step["start"]["archetype"]["rr"] == "burst"
    assert step["start"]["destination"]["rr"] == {"x": 87.0, "y": 25.0}


def _full_lineups():
    off = {
        "PG": _player("bh", 45, 15),
        "SG": _player("sg", 50, 20),
        "SF": _player("sf", 48, 30),
        "PF": _player("rr", 20, 40),
        "C": _player("reb", 35, 25),
    }
    deff = {
        "PG": _player("d1", 70, 25),
        "SG": _player("d2", 72, 20),
        "SF": _player("d3", 74, 30),
        "PF": _player("d4", 76, 15),
        "C": _player("d5", 78, 35),
    }
    return off, deff


def test_is_lane_pass_to_rr_resolution_turn_triangle_quick_shot():
    turn = {
        "fast_break_play": "triangle",
        "rim_runner_pass_attempted": True,
        "result_type": "MISS",
    }
    assert is_lane_pass_to_rr_resolution_turn(turn, {}) is True


def test_is_lane_pass_to_rr_resolution_turn_triangle_setup_tree():
    turn = {"fast_break_play": "triangle", "rim_runner_pass_attempted": False}
    roles = {"triangle_setup_phase": {"ball_handler_id": "bh"}}
    assert is_lane_pass_to_rr_resolution_turn(turn, roles) is False


def test_triangle_lane_pass_miss_builds_animation_steps():
    off, deff = _full_lineups()
    game = SimpleNamespace(
        game_state={
            "time_remaining": 420.0,
            "shot_clock_remaining": 24.0,
            "_is_full_simulation": False,
        },
        offense_team=SimpleNamespace(lineup=off, team_id="home"),
        defense_team=SimpleNamespace(lineup=deff, team_id="away"),
    )
    turn_result = {
        "fast_break_play": "triangle",
        "result_type": "MISS",
        "rim_runner_pass_attempted": True,
        "rim_runner_fb_open": True,
        "rebound_type": "DREB",
        "animations": [],
        "shooter": off["PF"],
        "defender": deff["PG"],
        "roles": {
            "rim_runner_burst_phase": {
                "rr_id": "rr",
                "outlet_receiver_id": "bh",
                "outlet_passer_id": None,
                "skip_outlet_pass": True,
                "rr_to": {"x": 30.0, "y": 40.0, "movement_archetype": "sprint"},
                "receiver_to": {"x": 45.0, "y": 15.0},
                "other_players": [],
                "is_away_offense": False,
            },
            "shooter": off["PF"],
            "ball_handler": off["PG"],
        },
    }

    steps = build_triangle_animation_steps(turn_result, game)

    assert steps is not None
    assert len(steps) >= 3
    terminal = steps[-1]["end"]["next"]
    assert terminal.get("kind") == "turn_stop"
    assert terminal.get("event") == "SHOT_ATTEMPT"
    assert terminal.get("payload", {}).get("schema_rendered_arc") is True
