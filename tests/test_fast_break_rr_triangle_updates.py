from types import SimpleNamespace

from BackEnd.engine.rim_runner_fast_break import (
    _resolve_rr_burst_destination,
    _resolve_triangle_setup_payload,
)
from BackEnd.engine.rim_runner_step_emitter import (
    LANE_PASS_LEAD_RAW_THRESHOLD,
    _build_burst_step,
    _build_lane_pass_step,
    _build_outlet_pass_step,
    _build_shot_motion_step,
    _calculate_lane_pass_raw_score,
    _lane_pass_getback_targets,
    is_lane_pass_to_rr_resolution_turn,
)
from BackEnd.engine.triangle_step_emitter import (
    _build_parallel_move_step,
    _build_triangle_shot_motion_step,
    _closeout_contest_coord,
    build_triangle_animation_steps,
)
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


def test_lane_pass_raw_score_includes_fb_efficiency():
    bh = _player("bh", 45, 15, ag=50, iq=50, ch=50)
    bh.attributes = {"PS": 50, "ST": 50, "IQ": 50, "AG": 50, "CH": 50}
    with __import__("unittest").mock.patch(
        "BackEnd.engine.rim_runner_step_emitter.random.randint", return_value=1
    ):
        assert _calculate_lane_pass_raw_score(bh, 5) == 55.0


def test_lane_pass_getback_targets_two_defenders():
    basket = {"x": 87.0, "y": 25.0}
    coords = {
        "gb_near": {"x": 70.0, "y": 25.0},
        "gb_far": {"x": 50.0, "y": 25.0},
    }
    targets = _lane_pass_getback_targets(
        ["gb_near", "gb_far"],
        coords,
        rr_y=30.0,
        is_away_offense=False,
        basket_spot=basket,
    )
    assert targets["gb_near"] == basket
    assert targets["gb_far"]["x"] == 80.0
    assert targets["gb_far"]["y"] == 32.0


def test_lane_pass_step_lead_pass_moves_help_defenders():
    off = {
        "PG": _player("bh", 45, 15, ag=50, iq=80, ch=80),
        "PF": _player("rr", 60, 30, ag=80, iq=80, ch=80),
        "SG": _player("trail", 40, 25, ag=50, iq=50, ch=50),
    }
    deff = {
        "PG": _player("gb1", 55, 26, ag=70, iq=50, ch=50),
        "SG": _player("gb2", 50, 20, ag=70, iq=50, ch=50),
    }
    start_coords = {
        "bh": {"x": 45.0, "y": 15.0},
        "rr": {"x": 60.0, "y": 30.0},
        "trail": {"x": 40.0, "y": 25.0},
        "gb1": {"x": 55.0, "y": 26.0},
        "gb2": {"x": 50.0, "y": 20.0},
    }
    fb_roles = {
        "getback_player_ids": ["gb1", "gb2"],
        "rim_runner_burst_phase": {
            "outlet_receiver_id": "bh",
            "rr_id": "rr",
            "rr_to": {"x": 87.0, "y": 25.0, "movement_archetype": "sprint"},
            "fb_efficiency": 0,
        },
    }
    turn_result = {"fast_break_play": "rim_runner", "rim_runner_pass_attempted": True}

    with __import__("unittest").mock.patch(
        "BackEnd.engine.rim_runner_step_emitter._calculate_lane_pass_raw_score",
        return_value=float(LANE_PASS_LEAD_RAW_THRESHOLD + 1),
    ):
        step = _build_lane_pass_step(
            turn_result=turn_result,
            fb_roles=fb_roles,
            off_lineup=off,
            def_lineup=deff,
            step_start_coords=start_coords,
            is_away_offense=False,
            clock_remaining_at_start=400.0,
            shot_clock_remaining_at_start=24.0,
            next_step_index=3,
        )

    assert step is not None
    assert step["start"]["pass_grid_per_game_second"] == 40.0
    assert step["start"]["ball_arrival_coord"] is not None
    assert step["end"]["coords"]["rr"] == step["start"]["ball_arrival_coord"]
    assert step["end"]["coords"]["rr"]["x"] < 87.0
    assert step["start"]["destination"]["rr"]["x"] == 87.0
    assert step["start"]["destination"]["trail"]["x"] == 87.0
    assert step["start"]["destination"]["gb1"]["x"] == 87.0
    assert step["start"]["destination"]["gb2"]["x"] == 80.0
    assert step["start"]["action"]["trail"] == "cut"
    assert step["start"]["archetype"]["trail"] == "standard"
    assert step["end"]["time_elapsed"] == step["start"]["advance_trigger"]["T_game_seconds"]
    assert step["start"]["advance_trigger"]["condition"] == "ball_reaches_player"


def test_lane_pass_step_no_lead_passes_to_rr_start():
    off = {"PG": _player("bh", 45, 15), "PF": _player("rr", 60, 30)}
    deff = {}
    start_coords = {
        "bh": {"x": 45.0, "y": 15.0},
        "rr": {"x": 60.0, "y": 30.0},
    }
    fb_roles = {
        "getback_player_ids": [],
        "rim_runner_burst_phase": {
            "outlet_receiver_id": "bh",
            "rr_id": "rr",
            "rr_to": {"x": 87.0, "y": 25.0, "movement_archetype": "sprint"},
            "fb_efficiency": 0,
        },
    }
    turn_result = {"fast_break_play": "rim_runner", "rim_runner_pass_attempted": True}

    with __import__("unittest").mock.patch(
        "BackEnd.engine.rim_runner_step_emitter._calculate_lane_pass_raw_score",
        return_value=float(LANE_PASS_LEAD_RAW_THRESHOLD),
    ):
        step = _build_lane_pass_step(
            turn_result=turn_result,
            fb_roles=fb_roles,
            off_lineup=off,
            def_lineup=deff,
            step_start_coords=start_coords,
            is_away_offense=False,
            clock_remaining_at_start=400.0,
            shot_clock_remaining_at_start=24.0,
            next_step_index=3,
        )

    assert step is not None
    assert step["start"]["pass_grid_per_game_second"] == 30.0
    assert step["start"]["advance_trigger"]["metadata"]["target_coords"] == start_coords["rr"]
    assert step["end"]["coords"]["rr"] == start_coords["rr"]
    assert step["start"]["ball_arrival_coord"] == start_coords["rr"]


def test_triangle_shot_motion_shooter_ends_at_authoritative_shot_spot():
    """RR (shooter) must shoot from the backend ``shot_spot``, never a
    legacy ``capture_fast_break_animation`` position. Regression for the
    Triangle ``rr_post`` bug where the RR caught on the block but jetted to a
    stale mirrored spot on the opposite half after a mid-game resume."""
    off = {
        "PG": _player("bh", 30, 32),
        "PF": _player("rr", 14, 32),
        "SG": _player("corner", 20, 8),
    }
    deff = {
        "PG": _player("d_ball", 18, 34),
        "SG": _player("d_off", 22, 12),
    }
    start_coords = {
        "bh": {"x": 30.0, "y": 32.0},
        "rr": {"x": 14.0, "y": 32.0},
        "corner": {"x": 20.0, "y": 8.0},
        "d_ball": {"x": 18.0, "y": 34.0},
        "d_off": {"x": 22.0, "y": 12.0},
    }
    shot_spot = {"x": 14.0, "y": 32.0}
    fb_roles = {"shooter": off["PF"], "shot_spot": shot_spot}
    turn_result = {
        "fast_break_play": "triangle",
        "shooter": off["PF"],
        "defender": deff["PG"],
        # A stale legacy packet on the opposite half — must be IGNORED now.
        "animations": [
            {"playerId": "rr", "movement": [{"coords": {"x": 70.0, "y": 8.0}}]},
        ],
        "roles": fb_roles,
    }

    step = _build_triangle_shot_motion_step(
        turn_result=turn_result,
        fb_roles=fb_roles,
        off_lineup=off,
        def_lineup=deff,
        step_start_coords=start_coords,
        clock_remaining_at_start=300.0,
        shot_clock_remaining_at_start=18.0,
    )

    assert step is not None
    # Shooter is pinned to the authoritative shot spot (the block), not {70, 8}.
    assert step["end"]["coords"]["rr"] == shot_spot
    assert step["start"]["action"]["rr"] == "shoot"
    assert step["start"]["advance_trigger"]["metadata"]["target_coords"] == shot_spot
    # Off-ball players hold their post-decision positions (no legacy movement).
    assert step["end"]["coords"]["corner"] == start_coords["corner"]
    assert step["end"]["coords"]["d_off"] == start_coords["d_off"]
    assert step["start"]["action"]["corner"] == "stationary"
    # The ball-defender contests toward the shooter (deterministic geo closeout).
    assert step["start"]["action"]["d_ball"] == "guard_ball"


def test_closeout_contest_coord_stops_short_of_shot_spot():
    # Defender far from the shot spot ends ~2 grid units short of it.
    contest = _closeout_contest_coord({"x": 40.0, "y": 32.0}, {"x": 14.0, "y": 32.0})
    assert contest == {"x": 16.0, "y": 32.0}
    # Defender already within standoff stays put.
    stay = _closeout_contest_coord({"x": 15.0, "y": 32.0}, {"x": 14.0, "y": 32.0})
    assert stay == {"x": 15.0, "y": 32.0}


def test_rr_lane_pass_shot_motion_shooter_ends_at_authoritative_shot_spot():
    """RR lane-pass quick shot: the shooter must render at the authoritative
    ``shot_spot`` (not a legacy packet position). Hardens the one reachable
    non-drive-resolution RR shot path against the Triangle-class jetting bug."""
    off = {
        "PG": _player("bh", 30, 25),
        "PF": _player("rr", 14, 32),
        "SG": _player("trail", 22, 8),
    }
    deff = {
        "PG": _player("d_ball", 40, 32),
        "SG": _player("d_off", 24, 12),
    }
    start_coords = {
        "bh": {"x": 30.0, "y": 25.0},
        "rr": {"x": 14.0, "y": 32.0},
        "trail": {"x": 22.0, "y": 8.0},
        "d_ball": {"x": 40.0, "y": 32.0},
        "d_off": {"x": 24.0, "y": 12.0},
    }
    shot_spot = {"x": 14.0, "y": 32.0}
    fb_roles = {
        "rim_runner_burst_phase": {"rr_id": "rr"},
        "shot_spot": shot_spot,
    }
    turn_result = {
        "fast_break_play": "rim_runner",
        "result_type": "MISS",
        "defender": deff["PG"],
        "roles": fb_roles,
    }

    step = _build_shot_motion_step(
        turn_result=turn_result,
        fb_roles=fb_roles,
        off_lineup=off,
        def_lineup=deff,
        step_start_coords=start_coords,
        clock_remaining_at_start=300.0,
        shot_clock_remaining_at_start=18.0,
    )

    assert step is not None
    assert step["end"]["coords"]["rr"] == shot_spot
    assert step["start"]["action"]["rr"] == "shoot"
    assert step["start"]["advance_trigger"]["metadata"]["target_coords"] == shot_spot
    # Off-ball players hold; ball defender contests toward the shooter.
    assert step["end"]["coords"]["trail"] == start_coords["trail"]
    assert step["end"]["coords"]["d_off"] == start_coords["d_off"]
    assert step["start"]["action"]["d_ball"] == "guard_ball"
    # Defender closed toward the shot spot (moved in from x=40 toward x=14).
    assert step["end"]["coords"]["d_ball"]["x"] < 40.0


def _parallel_move_fixture():
    """Gate player has a short run; the pass receiver has a much longer one."""
    off = {
        "PG": _player("bh", 45, 25),
        "PF": _player("rr", 20, 40),
    }
    deff = {"PG": _player("d1", 70, 25)}
    start_coords = {
        "bh": {"x": 45.0, "y": 25.0},
        "rr": {"x": 20.0, "y": 40.0},
        "d1": {"x": 70.0, "y": 25.0},
    }
    movers = [
        ("bh", {"x": 50.0, "y": 25.0}, "sprint", "handle_ball"),
        ("rr", {"x": 60.0, "y": 10.0}, "sprint", "cut"),
    ]
    return off, deff, start_coords, movers


def test_parallel_move_step_clamps_receiver_without_arrival_gate():
    """Baseline: gating only on the (fast-finishing) ball handler clamps a
    longer-running receiver short of his spot — the residual that later gets
    jetted away by the ball-flight-timed pass step."""
    off, deff, start_coords, movers = _parallel_move_fixture()
    step = _build_parallel_move_step(
        step_start_coords=start_coords,
        movers=movers,
        gate_player_id="bh",
        ball_owner_id="bh",
        off_lineup=off,
        def_lineup=deff,
        clock_remaining_at_start=300.0,
        shot_clock_remaining_at_start=18.0,
        next_step={"kind": "next_step", "index": 2},
    )
    assert step is not None
    # Receiver is clamped short of his target (residual remains).
    assert step["end"]["coords"]["rr"] != {"x": 60.0, "y": 10.0}


def test_parallel_move_step_arrival_gate_lands_receiver_on_spot():
    """Fix: naming the receiver in ``arrival_player_ids`` extends T to his
    traversal, so he fully reaches the pass spot within the step — the next
    pass step starts him on-spot (no residual → no jet)."""
    off, deff, start_coords, movers = _parallel_move_fixture()
    baseline = _build_parallel_move_step(
        step_start_coords=start_coords,
        movers=movers,
        gate_player_id="bh",
        ball_owner_id="bh",
        off_lineup=off,
        def_lineup=deff,
        clock_remaining_at_start=300.0,
        shot_clock_remaining_at_start=18.0,
        next_step={"kind": "next_step", "index": 2},
    )
    gated = _build_parallel_move_step(
        step_start_coords=start_coords,
        movers=movers,
        gate_player_id="bh",
        ball_owner_id="bh",
        off_lineup=off,
        def_lineup=deff,
        clock_remaining_at_start=300.0,
        shot_clock_remaining_at_start=18.0,
        next_step={"kind": "next_step", "index": 2},
        arrival_player_ids=["rr"],
    )
    assert gated is not None and baseline is not None
    # Receiver lands exactly on his pass target.
    assert gated["end"]["coords"]["rr"] == {"x": 60.0, "y": 10.0}
    # T was extended to cover the slower receiver's full run.
    assert gated["end"]["time_elapsed"] > baseline["end"]["time_elapsed"]
    # The gate player still reaches his (shorter) target regardless.
    assert gated["end"]["coords"]["bh"] == {"x": 50.0, "y": 25.0}
