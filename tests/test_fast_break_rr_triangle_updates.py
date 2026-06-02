from types import SimpleNamespace

from BackEnd.engine.rim_runner_fast_break import (
    _resolve_rr_burst_destination,
    _resolve_triangle_setup_payload,
)
from BackEnd.engine.rim_runner_step_emitter import _build_burst_step
from BackEnd.utils.shared import calc_ag_segment_seconds


def _player(player_id, x, y, *, ag=50, iq=50, ch=50):
    return SimpleNamespace(
        player_id=player_id,
        coords={"x": x, "y": y},
        attributes={"AG": ag, "IQ": iq, "CH": ch},
    )


def test_rr_burst_destination_uses_wing_and_sprint_delta_without_dynamic_base():
    destination, dynamic_base = _resolve_rr_burst_destination(
        rr_x0=20,
        rr_y0=30,
        outlet_receiver_target_x=45,
        dx_burst=10,
        is_away_offense=False,
        most_recent_shot_turn={"ball_bounce_x": 80},
    )

    assert dynamic_base is None
    assert destination == {"x": 30.0, "y": 40.0}


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
    assert destination == {"x": 69.0, "y": 40.0}


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
    assert destination == {"x": 33.0, "y": 10.0}


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


def test_rim_runner_burst_step_uses_payload_sprint_archetype():
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
            "rr_to": {"x": 30.0, "y": 40.0, "movement_archetype": "sprint"},
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
    assert step["start"]["tween_durations"]["rr"] == step["end"]["time_elapsed"]
    assert step["end"]["time_elapsed"] > 0.5
