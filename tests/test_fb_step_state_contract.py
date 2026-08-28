"""Fast Break UESS / StepState contract tests.

These tests lock the Fast Break AnimationStep contract and verify the additive
FastBreakStepState bridge without requiring a full game simulation.
"""

import copy
from types import SimpleNamespace

import pytest

from BackEnd.engine.fb_drive_step_emitter import build_fb_drive_resolution_steps
from BackEnd.engine.fb_outlet_pass_step_emitter import build_fb_outlet_pass_step
from BackEnd.engine.fb_step_state import (
    build_fast_break_step_states,
    project_animation_step_through_fast_break_state,
    project_fast_break_step_states_to_animation_steps,
)
from BackEnd.engine.fb_uess_debug import build_fb_uess_summary
from BackEnd.engine.after_steal_fast_break_step_emitter import (
    build_after_steal_fast_break_animation_steps,
)
from BackEnd.engine.covert_release_step_emitter import build_covert_release_animation_steps
from BackEnd.engine.rim_runner_step_emitter import (
    _build_finisher_drive_resolution_steps,
    build_rim_runner_animation_steps,
)
from BackEnd.engine.triangle_step_emitter import build_triangle_animation_steps
from BackEnd.models.turn_manager import TurnManager
from tests.test_utils import build_mock_game


POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _player(pid, x=50.0, y=25.0):
    attrs = {k: 60 for k in ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "CH")}
    return SimpleNamespace(player_id=pid, attributes=attrs, coords={"x": x, "y": y})


def _lineup(prefix):
    return {pos: _player(f"{prefix}-{pos}") for pos in POSITIONS}


def _game():
    off_lineup = _lineup("off")
    def_lineup = _lineup("def")
    offense = SimpleNamespace(team_id="home", name="Offense", lineup=off_lineup)
    defense = SimpleNamespace(team_id="away", name="Defense", lineup=def_lineup)
    coords = _start_coords(off_lineup, def_lineup)
    return SimpleNamespace(
        offense_team=offense,
        defense_team=defense,
        home_team=offense,
        away_team=defense,
        game_state={"time_remaining": 420.0, "shot_clock_remaining": 25.0},
        turns=[{"final_coords": coords, "final_ball_handler_id": "off-PG"}],
    )


def _start_coords(off_lineup, def_lineup):
    coords = {}
    for idx, pos in enumerate(POSITIONS):
        off = off_lineup[pos]
        deff = def_lineup[pos]
        off.coords = {"x": 44.0 + idx * 2, "y": 17.0 + idx * 4}
        deff.coords = {"x": 58.0 + idx * 2, "y": 17.0 + idx * 4}
        coords[off.player_id] = dict(off.coords)
        coords[deff.player_id] = dict(deff.coords)
    return coords


def _end_coords(start_coords, shooter_id="off-PG"):
    end = {pid: dict(coord) for pid, coord in start_coords.items()}
    end[shooter_id] = {"x": 88.0, "y": 25.0}
    end["def-PG"] = {"x": 82.0, "y": 25.0}
    return end


def _turn_result(*, result_type="MAKE", outcome="NO_MEET", play_key="covert_release"):
    shooter_id = "off-PG"
    result = {
        "result_type": result_type,
        "fast_break_play": play_key,
        "shooter_id": shooter_id,
        "shooter": SimpleNamespace(player_id=shooter_id),
        "ball_handler": SimpleNamespace(player_id=shooter_id),
        "bh_target": {"x": 88.0, "y": 25.0},
        "t_shooter_game_seconds": 1.5,
        "shot_score_pre_defense": 100,
        "shot_defense_score_for_sfx": 0,
        "shot_type": "attack",
        "shot_variant": None,
        "roles": {
            "ball_handler": SimpleNamespace(player_id=shooter_id),
            "is_away_offense": False,
        },
        "fb_drive_resolution": {
            "outcome": outcome,
            "t_drive_game_seconds": 1.5,
            "shot_defender_id": "def-PG",
            "defender_end_coords": {"def-PG": {"x": 82.0, "y": 25.0}},
            "defender_archetypes": {"def-PG": "sprint"},
        },
    }
    if outcome == "POS_O":
        result["fb_drive_resolution"].update(
            {
                "bh_path_knots": [
                    {"x": 50.0, "y": 25.0},
                    {"x": 66.0, "y": 25.0},
                    {"x": 74.0, "y": 27.0},
                    {"x": 88.0, "y": 25.0},
                ],
                "path_segment_game_seconds": [0.6, 0.4, 0.5],
            }
        )
    if outcome == "NEUTRAL":
        result.update(
            {
                "result_type": "DEFENSIVE_STOP",
                "meet_coords": {"x": 70.0, "y": 25.0},
                "stop_decision_action": "HCO",
            }
        )
        result["fb_drive_resolution"].update(
            {
                "meet_x": 70.0,
                "meet_y": 25.0,
                "t_meet_game_seconds": 1.0,
                "stopper_id": "def-PG",
                "stop_decision": {"action": "HCO"},
            }
        )
    if outcome == "DEAD BALL":
        result.update(
            {
                "result_type": "DEAD BALL",
                "meet_coords": {"x": 70.0, "y": 25.0},
                "victim_id": shooter_id,
                "dead_ball_turnover_label": "TRAVEL",
            }
        )
        result["fb_drive_resolution"].update(
            {
                "meet_x": 70.0,
                "meet_y": 25.0,
                "t_meet_game_seconds": 1.0,
                "stopper_id": "def-PG",
            }
        )
    return result


def _rr_triangle_live_turn_result(game, play_key):
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    return {
        "fast_break_play": play_key,
        "result_type": "MISS",
        "rim_runner_pass_attempted": True,
        "rim_runner_fb_open": True,
        "rebound_type": "DREB",
        "animations": [],
        "shooter": off_lineup["PF"],
        "defender": def_lineup["PG"],
        "roles": {
            "fast_break_play": play_key,
            "rim_runner_burst_phase": {
                "rr_id": "off-PF",
                "outlet_receiver_id": "off-PG",
                "outlet_passer_id": None,
                "skip_outlet_pass": True,
                "rr_to": {"x": 87.0, "y": 25.0, "movement_archetype": "sprint"},
                "receiver_to": {"x": 50.0, "y": 25.0},
                "other_players": [],
                "is_away_offense": False,
                "fb_efficiency": 0,
            },
            "shooter": off_lineup["PF"],
            "ball_handler": off_lineup["PG"],
        },
    }


def _assert_schema_chain(steps):
    assert steps
    for idx, step in enumerate(steps):
        assert "start" in step
        assert "end" in step
        assert isinstance(step["start"].get("coords"), dict)
        assert isinstance(step["end"].get("coords"), dict)
        assert "ball" in step["start"]
        assert "ball" in step["end"]
        assert "clock" in step["start"]
        assert "clock" in step["end"]
        nxt = step["end"].get("next")
        assert isinstance(nxt, dict)
        if nxt.get("kind") == "next_step":
            # 999 is the existing implicit-end sentinel used by several schema
            # emitters; otherwise the chain should advance one step at a time.
            assert nxt.get("index") in (idx + 1, 999)
        elif nxt.get("kind") == "turn_stop":
            assert idx == len(steps) - 1
            assert nxt.get("event")
        else:
            assert nxt.get("kind") in ("end_of_turn",)


def _schema_clock_burn(steps):
    start = float(steps[0]["start"]["clock"]["clock_remaining"])
    end = float(steps[-1]["end"]["clock"]["clock_remaining"])
    return max(0.0, start - end)


def _strip_fb_state(steps):
    stripped = []
    for step in steps:
        clone = dict(step)
        clone.pop("_fb_step_state", None)
        stripped.append(clone)
    return stripped


def _assert_fb_projection_parity(steps, *, play_key, result_type):
    original = _strip_fb_state(copy.deepcopy(steps))
    result = {
        "current_turn": "FAST_BREAK",
        "fast_break_play": play_key,
        "result_type": result_type,
        "animation_steps": steps,
    }
    states = build_fast_break_step_states(result)
    projected = project_fast_break_step_states_to_animation_steps(states)

    assert len(states) == len(original)
    assert result["fb_step_states"] == states
    assert all(step.get("_fb_step_state") for step in steps)
    assert _strip_fb_state(projected) == original
    assert _strip_fb_state(steps) == original
    assert {state["turn_type"] for state in states} == {"FAST_BREAK"}
    assert {state["play_key"] for state in states} == {play_key}


@pytest.mark.parametrize(
    "family,kind_prefix,play_key,stamp,suppress_stinger,crash,spread",
    [
        ("covert_release", "covert_release", "covert_release", True, False, True, True),
        ("rim_runner", "rim_runner", "rim_runner", False, False, True, True),
        ("triangle", "rim_runner", "triangle", False, False, True, True),
        ("after_steal", "after_steal", "after_steal", True, True, False, False),
    ],
)
@pytest.mark.parametrize("outcome", ["NO_MEET", "POS_O", "NEUTRAL", "DEAD BALL"])
def test_fb_drive_schema_contract_for_all_families(
    family,
    kind_prefix,
    play_key,
    stamp,
    suppress_stinger,
    crash,
    spread,
    outcome,
):
    game = _game()
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    start_coords = _start_coords(off_lineup, def_lineup)
    turn_result = _turn_result(outcome=outcome, play_key=play_key)
    end_coords = _end_coords(start_coords)
    if family == "after_steal":
        # After-Steal resolver pre-authors spread destinations before calling
        # the universal drive helper.
        turn_result["after_steal_end_coords"] = end_coords

    steps = build_fb_drive_resolution_steps(
        turn_result=turn_result,
        game=game,
        start_coords=start_coords,
        end_coords=end_coords,
        stealer_id="off-PG",
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        is_away_offense=False,
        clock_remaining=420.0,
        shot_clock_remaining=25.0,
        fb_roles=turn_result.get("roles") or {},
        kind_prefix=kind_prefix,
        stamp_fb_start_announcement=stamp,
        suppress_stinger=suppress_stinger,
        crash_off_ball_to_basket=crash,
        author_offball_spread=spread,
    )

    assert steps is not None, f"{family} {outcome} should emit FB schema"
    _assert_schema_chain(steps)
    assert all(step.get("_fb_step_state") for step in steps)
    assert _schema_clock_burn(steps) >= 0
    assert "off-PG" in steps[-1]["end"]["coords"]
    if outcome == "DEAD BALL":
        assert steps[-1]["end"]["next"]["kind"] == "turn_stop"
        assert steps[-1]["end"]["next"]["event"] == "DEAD_BALL_TURNOVER"


def _neutral_stop_pass_turn(*, receiver_id="off-SG"):
    """NEUTRAL meet + kick-ahead pass + MAKE — the after_steal_stop_pass path."""
    result = _turn_result(result_type="MAKE", outcome="NEUTRAL", play_key="after_steal")
    result["result_type"] = "MAKE"
    result["stop_decision_action"] = "pass"
    result["pass_receiver_id"] = receiver_id
    result["fb_drive_resolution"]["stop_decision"] = {"action": "pass"}
    return result


def test_fb_drive_stop_pass_next_step_does_not_self_loop():
    """Regression: stop-pass used next_step_index=len(steps) before append,
    so the pass step pointed at itself and the FE replayed pass SFX forever."""
    game = _game()
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    start_coords = _start_coords(off_lineup, def_lineup)
    turn_result = _neutral_stop_pass_turn(receiver_id="off-SG")
    end_coords = _end_coords(start_coords, shooter_id="off-SG")

    steps = build_fb_drive_resolution_steps(
        turn_result=turn_result,
        game=game,
        start_coords=start_coords,
        end_coords=end_coords,
        stealer_id="off-PG",
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        is_away_offense=False,
        clock_remaining=235.0,
        shot_clock_remaining=30.0,
        fb_roles=turn_result.get("roles") or {},
        kind_prefix="after_steal",
        stamp_fb_start_announcement=True,
        suppress_stinger=True,
        crash_off_ball_to_basket=False,
        author_offball_spread=False,
    )

    assert steps is not None
    pass_steps = [
        (idx, step)
        for idx, step in enumerate(steps)
        if (step.get("start") or {}).get("advance_trigger", {}).get("metadata", {}).get(
            "reason"
        )
        == "after_steal_stop_pass"
    ]
    assert pass_steps, "expected a stop-pass step"
    idx, pass_step = pass_steps[0]
    nxt = pass_step["end"]["next"]
    assert nxt.get("kind") == "next_step"
    assert nxt.get("index") == idx + 1
    assert nxt.get("index") != idx
    ball = pass_step["start"]["ball"]
    assert ball["from_player_id"] == "off-PG"
    assert ball["to_player_id"] == "off-SG"
    _assert_schema_chain(steps)


def test_fb_drive_stop_pass_skips_self_pass():
    """A stop-pass whose receiver is the ball handler is a 0-distance self-pass;
    skip it so we don't emit pass SFX for a player throwing to himself."""
    game = _game()
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    start_coords = _start_coords(off_lineup, def_lineup)
    turn_result = _neutral_stop_pass_turn(receiver_id="off-PG")
    end_coords = _end_coords(start_coords)

    steps = build_fb_drive_resolution_steps(
        turn_result=turn_result,
        game=game,
        start_coords=start_coords,
        end_coords=end_coords,
        stealer_id="off-PG",
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        is_away_offense=False,
        clock_remaining=235.0,
        shot_clock_remaining=30.0,
        fb_roles=turn_result.get("roles") or {},
        kind_prefix="after_steal",
        stamp_fb_start_announcement=True,
        suppress_stinger=True,
        crash_off_ball_to_basket=False,
        author_offball_spread=False,
    )

    assert steps is not None
    reasons = [
        (step.get("start") or {}).get("advance_trigger", {}).get("metadata", {}).get(
            "reason"
        )
        for step in steps
    ]
    assert "after_steal_stop_pass" not in reasons
    _assert_schema_chain(steps)


@pytest.mark.parametrize(
    "wrapper,play_key",
    [
        ("covert_release", "covert_release"),
        ("after_steal", "after_steal"),
    ],
)
def test_fb_step_state_bridge_projects_family_wrapper_drive_schema(wrapper, play_key):
    game = _game()
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    start_coords = _start_coords(off_lineup, def_lineup)
    turn_result = _turn_result(outcome="NO_MEET", play_key=play_key)
    end_coords = _end_coords(start_coords)
    if wrapper == "covert_release":
        turn_result["cr_end_coords"] = end_coords
        turn_result["roles"].update(
            {
                "outlet_passer": None,
                "outlet_receiver": None,
                "is_away_offense": False,
            }
        )
        steps = build_covert_release_animation_steps(turn_result, game)
    else:
        turn_result["after_steal_end_coords"] = end_coords
        steps = build_after_steal_fast_break_animation_steps(turn_result, game)

    assert steps is not None
    _assert_schema_chain(steps)
    _assert_fb_projection_parity(
        steps,
        play_key=play_key,
        result_type=turn_result["result_type"],
    )


@pytest.mark.parametrize("play_key", ["rim_runner", "triangle"])
def test_fb_step_state_bridge_projects_rr_triangle_finisher_adapter_schema(play_key):
    game = _game()
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    start_coords = _start_coords(off_lineup, def_lineup)
    turn_result = _turn_result(outcome="NO_MEET", play_key=play_key)
    turn_result["rr_end_coords"] = _end_coords(start_coords)
    turn_result["shooter"] = off_lineup["PG"]
    fb_roles = {
        "fast_break_play": play_key,
        "shooter": off_lineup["PG"],
        "rim_runner_burst_phase": {"rr_id": "off-PG"},
    }

    steps = _build_finisher_drive_resolution_steps(
        turn_result=turn_result,
        game=game,
        start_coords=start_coords,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        is_away_offense=False,
        clock_remaining=420.0,
        shot_clock_remaining=25.0,
        fb_roles=fb_roles,
    )

    assert steps is not None
    _assert_schema_chain(steps)
    _assert_fb_projection_parity(
        steps,
        play_key=play_key,
        result_type=turn_result["result_type"],
    )


@pytest.mark.parametrize(
    "play_key,builder",
    [
        ("rim_runner", build_rim_runner_animation_steps),
        ("triangle", build_triangle_animation_steps),
    ],
)
def test_fb_top_level_rr_triangle_live_paths_do_not_fall_back(play_key, builder):
    game = _game()
    turn_result = _rr_triangle_live_turn_result(game, play_key)

    steps = builder(turn_result, game)

    assert steps is not None
    assert "fb_emitter_fallback_reason" not in turn_result
    _assert_schema_chain(steps)


@pytest.mark.parametrize(
    "family,builder,bad_result,expected_reason",
    [
        (
            "rim_runner",
            build_rim_runner_animation_steps,
            {"fast_break_play": "rim_runner", "result_type": "MISS", "roles": {}},
            "rim_runner:missing_burst_phase",
        ),
        (
            "triangle",
            build_triangle_animation_steps,
            {"fast_break_play": "triangle", "result_type": "MISS", "roles": {}},
            "triangle:missing_burst_phase",
        ),
        (
            "covert_release",
            build_covert_release_animation_steps,
            {"fast_break_play": "covert_release", "result_type": "MISS", "roles": {}},
            "covert_release:missing_bh_id",
        ),
        (
            "after_steal",
            build_after_steal_fast_break_animation_steps,
            {"fast_break_play": "after_steal", "result_type": "DEAD BALL"},
            "after_steal:unsupported_result_type",
        ),
    ],
)
def test_fb_public_builders_stamp_explicit_fallback_reason(
    family,
    builder,
    bad_result,
    expected_reason,
):
    game = _game()

    steps = builder(bad_result, game)

    assert steps is None, family
    assert bad_result.get("fb_emitter_fallback_reason") == expected_reason


@pytest.mark.parametrize(
    "family,mover_targets",
    [
        (
            "rim_runner",
            {
                "off-PF": ({"x": 72.0, "y": 25.0}, "sprint", "cut"),
                "def-PF": ({"x": 74.0, "y": 25.0}, "sprint", "guard_offball"),
            },
        ),
        (
            "covert_release",
            {
                "off-SG": ({"x": 62.0, "y": 21.0}, "standard", "cut"),
                "def-SG": ({"x": 64.0, "y": 21.0}, "standard", "guard_offball"),
            },
        ),
    ],
)
def test_fb_outlet_pass_schema_contract_for_shared_core(family, mover_targets):
    game = _game()
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    start_coords = _start_coords(off_lineup, def_lineup)

    step = build_fb_outlet_pass_step(
        passer_id="off-C",
        receiver_id="off-PG",
        start_coords=start_coords,
        mover_targets=mover_targets,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        clock_remaining_at_start=420.0,
        shot_clock_remaining_at_start=25.0,
        next_step_index=1,
        outlet_score=80,
    )

    assert step is not None
    _assert_schema_chain([step])
    assert step.get("_fb_step_state")
    trigger = step["start"]["advance_trigger"]
    assert trigger["condition"] == "ball_reaches_player"
    assert trigger["metadata"]["from_player_id"] == "off-C"
    assert trigger["metadata"]["to_player_id"] == "off-PG"
    assert step["start"]["ball"]["owner_player_id"] == "off-C"
    assert step["end"]["ball"]["owner_player_id"] == "off-PG"


@pytest.mark.parametrize(
    "family,kind_prefix,play_key,stamp,suppress_stinger,crash,spread",
    [
        ("covert_release", "covert_release", "covert_release", True, False, True, True),
        ("rim_runner", "rim_runner", "rim_runner", False, False, True, True),
        ("triangle", "rim_runner", "triangle", False, False, True, True),
        ("after_steal", "after_steal", "after_steal", True, True, False, False),
    ],
)
@pytest.mark.parametrize("outcome", ["NO_MEET", "DEAD BALL"])
def test_fb_step_state_bridge_projects_drive_schema_without_behavior_change(
    family,
    kind_prefix,
    play_key,
    stamp,
    suppress_stinger,
    crash,
    spread,
    outcome,
):
    game = _game()
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    start_coords = _start_coords(off_lineup, def_lineup)
    turn_result = _turn_result(outcome=outcome, play_key=play_key)
    end_coords = _end_coords(start_coords)
    if family == "after_steal":
        turn_result["after_steal_end_coords"] = end_coords

    steps = build_fb_drive_resolution_steps(
        turn_result=turn_result,
        game=game,
        start_coords=start_coords,
        end_coords=end_coords,
        stealer_id="off-PG",
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        is_away_offense=False,
        clock_remaining=420.0,
        shot_clock_remaining=25.0,
        fb_roles=turn_result.get("roles") or {},
        kind_prefix=kind_prefix,
        stamp_fb_start_announcement=stamp,
        suppress_stinger=suppress_stinger,
        crash_off_ball_to_basket=crash,
        author_offball_spread=spread,
    )
    assert steps is not None

    _assert_fb_projection_parity(
        steps,
        play_key=play_key,
        result_type=turn_result["result_type"],
    )


def test_fb_step_state_bridge_projects_outlet_pass_without_behavior_change():
    game = _game()
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    start_coords = _start_coords(off_lineup, def_lineup)
    step = build_fb_outlet_pass_step(
        passer_id="off-C",
        receiver_id="off-PG",
        start_coords=start_coords,
        mover_targets={
            "off-PF": ({"x": 72.0, "y": 25.0}, "sprint", "cut"),
            "def-PF": ({"x": 74.0, "y": 25.0}, "sprint", "guard_offball"),
        },
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        clock_remaining_at_start=420.0,
        shot_clock_remaining_at_start=25.0,
        next_step_index=1,
        outlet_score=80,
    )
    assert step is not None

    original = _strip_fb_state([copy.deepcopy(step)])
    result = {
        "current_turn": "FAST_BREAK",
        "fast_break_play": "rim_runner",
        "result_type": "HCO",
        "animation_steps": [step],
    }
    states = build_fast_break_step_states(result)
    projected = project_fast_break_step_states_to_animation_steps(states)

    assert len(states) == 1
    assert step.get("_fb_step_state")
    assert _strip_fb_state(projected) == original
    assert _strip_fb_state([step]) == original


def test_project_single_animation_step_through_fast_break_state_preserves_schema():
    step = {
        "start": {
            "coords": {"off-PG": {"x": 50.0, "y": 25.0}},
            "destination": {"off-PG": {"x": 60.0, "y": 25.0}},
            "action": {"off-PG": "drive"},
            "archetype": {"off-PG": "standard"},
            "ball": {"owner_player_id": "off-PG"},
            "clock": {"clock_remaining": 420.0, "shot_clock_remaining": 25.0},
            "advance_trigger": {
                "condition": "player_reaches",
                "T_game_seconds": 1.0,
                "metadata": {"target_player_id": "off-PG"},
            },
        },
        "end": {
            "coords": {"off-PG": {"x": 60.0, "y": 25.0}},
            "ball": {"owner_player_id": "off-PG"},
            "time_elapsed": 1.0,
            "clock": {"clock_remaining": 419.0, "shot_clock_remaining": 24.0},
            "next": {"kind": "next_step", "index": 1},
        },
    }
    original = copy.deepcopy(step)

    projected = project_animation_step_through_fast_break_state(
        step,
        index=0,
        result={"current_turn": "FAST_BREAK", "fast_break_play": "after_steal"},
    )

    assert projected.get("_fb_step_state")
    assert _strip_fb_state([projected]) == [original]


def test_fb_uess_summary_reports_shared_observability_fields():
    result = {
        "result_type": "MAKE",
        "fast_break_play": "covert_release",
        "time_elapsed": 3,
        "animation_steps": [
            {
                "start": {
                    "ball": {"owner_player_id": "off-PG"},
                    "clock": {"clock_remaining": 420.0, "shot_clock_remaining": 25.0},
                },
                "end": {
                    "coords": {"off-PG": {"x": 60.0, "y": 25.0}},
                    "ball": {"owner_player_id": "off-PG"},
                    "clock": {"clock_remaining": 418.5, "shot_clock_remaining": 23.5},
                },
            },
            {
                "start": {
                    "ball": {"owner_player_id": "off-PG"},
                    "clock": {"clock_remaining": 418.5, "shot_clock_remaining": 23.5},
                },
                "end": {
                    "coords": {
                        "off-PG": {"x": 88.0, "y": 25.0},
                        "def-PG": {"x": 82.0, "y": 25.0},
                    },
                    "ball": {"owner_player_id": "off-PG"},
                    "clock": {"clock_remaining": 417.0, "shot_clock_remaining": 22.0},
                },
            },
        ],
        "fb_step_states": [{"index": 0}, {"index": 1}],
    }
    summary = build_fb_uess_summary(
        result,
        SimpleNamespace(game_id="game-1"),
        fallback_reason=None,
    )

    assert summary == {
        "game_id": "game-1",
        "fast_break_play": "covert_release",
        "result_type": "MAKE",
        "step_count": 2,
        "schema_clock_burn": 3.0,
        "time_elapsed": 3,
        "first_ball_owner": "off-PG",
        "final_ball_owner": "off-PG",
        "final_coords_count": 2,
        "fb_step_state_count": 2,
        "fallback_reason": None,
        "next_play_type": None,
        "is_full_simulation": False,
    }


def test_turn_manager_fast_break_branch_stamps_and_projects_fb_step_state(monkeypatch):
    game = build_mock_game()
    for team in (game.home_team, game.away_team):
        for player in team.lineup.values():
            player.stats.setdefault("game", {}).setdefault("MIN", 0)
    game.game_state["offensive_state"] = "FAST_BREAK"
    game.game_state["time_remaining"] = 420
    game.game_state["shot_clock_remaining"] = 25
    game.turns = [
        {
            "result_type": "MISS",
            "final_ball_coords": {"x": 50.0, "y": 25.0},
            "final_coords": {"off-PG": {"x": 50.0, "y": 25.0}},
        }
    ]
    step = {
        "start": {
            "coords": {"off-PG": {"x": 50.0, "y": 25.0}},
            "destination": {"off-PG": {"x": 60.0, "y": 25.0}},
            "action": {"off-PG": "drive"},
            "archetype": {"off-PG": "standard"},
            "ball": {"owner_player_id": "off-PG"},
            "clock": {"clock_remaining": 420.0, "shot_clock_remaining": 25.0},
            "advance_trigger": {
                "condition": "player_reaches",
                "T_game_seconds": 2.0,
                "metadata": {"target_player_id": "off-PG", "kind": "after_steal_drive"},
            },
        },
        "end": {
            "coords": {"off-PG": {"x": 60.0, "y": 25.0}},
            "ball": {"owner_player_id": "off-PG"},
            "time_elapsed": 2.0,
            "clock": {"clock_remaining": 418.0, "shot_clock_remaining": 23.0},
            "next": {"kind": "end_of_turn"},
        },
    }

    def fake_resolve_fast_break_logic(_game):
        return {
            "result_type": "DEFENSIVE_STOP",
            "fast_break_play": "after_steal",
            "time_elapsed": 99,
            "next_play_type": "HCO",
            "possession_flips": False,
            "animation_steps": [copy.deepcopy(step)],
        }

    monkeypatch.setattr(
        "BackEnd.models.turn_manager.resolve_fast_break_logic",
        fake_resolve_fast_break_logic,
    )

    result = TurnManager(game).run_micro_turn()

    assert result["current_turn"] == "FAST_BREAK"
    assert result["time_elapsed"] == 2
    assert result.get("fb_step_states")
    assert result["animation_steps"][0].get("_fb_step_state")
    assert _strip_fb_state(result["animation_steps"]) == [step]
