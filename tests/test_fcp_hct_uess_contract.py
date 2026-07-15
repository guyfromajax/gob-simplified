"""FCP/HCT UESS contract tests.

These tests intentionally exercise the shared dynamic HCT/FCP schema emitter
with small synthetic payloads. They are not full gameplay simulations; their job
is to lock the pressure-turn animation-step contract before the UESS update work.
"""

from types import SimpleNamespace

import pytest

from BackEnd.engine.dynamic_fcp_step_emitter import build_dynamic_fcp_animation_steps
from BackEnd.engine.dynamic_hct_step_emitter import build_dynamic_hct_animation_steps
from BackEnd.engine.pressure_step_state import (
    build_pressure_step_states,
    project_pressure_step_states_to_animation_steps,
)
from BackEnd.models.turn_manager import TurnManager


POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _player(pid):
    attrs = {k: 55 for k in ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "CH")}
    return SimpleNamespace(player_id=pid, attributes=attrs, coords={"x": 50.0, "y": 25.0})


def _game():
    off_lineup = {pos: _player(f"off_{pos.lower()}") for pos in POSITIONS}
    def_lineup = {pos: _player(f"def_{pos.lower()}") for pos in POSITIONS}
    offense = SimpleNamespace(team_id="home", lineup=off_lineup)
    defense = SimpleNamespace(team_id="away", lineup=def_lineup)
    prior_coords = {
        "off_pg": {"x": 42.0, "y": 25.0},
        "off_sg": {"x": 50.0, "y": 18.0},
        "off_sf": {"x": 50.0, "y": 32.0},
        "off_pf": {"x": 62.0, "y": 18.0},
        "off_c": {"x": 62.0, "y": 32.0},
        "def_pg": {"x": 45.0, "y": 25.0},
        "def_sg": {"x": 52.0, "y": 18.0},
        "def_sf": {"x": 52.0, "y": 32.0},
        "def_pf": {"x": 64.0, "y": 18.0},
        "def_c": {"x": 64.0, "y": 32.0},
    }
    return SimpleNamespace(
        offense_team=offense,
        defense_team=defense,
        away_team=defense,
        game_state={"time_remaining": 480.0, "shot_clock_remaining": 24.0},
        turns=[{"final_ball_handler_id": "off_pg", "final_coords": prior_coords}],
    )


def _base_payload(*, result_type="HCO", reason="hct_advance", fcp=False):
    segment = {
        "reason": reason,
        "step_label": reason,
        "off_end": {
            "PG": {"x": 48.0, "y": 25.0},
            "SG": {"x": 58.0, "y": 18.0},
            "SF": {"x": 58.0, "y": 32.0},
            "PF": {"x": 68.0, "y": 18.0},
            "C": {"x": 68.0, "y": 32.0},
        },
        "def_end": {
            "PG": {"x": 50.0, "y": 25.0},
            "SG": {"x": 60.0, "y": 18.0},
            "SF": {"x": 60.0, "y": 32.0},
            "PF": {"x": 70.0, "y": 18.0},
            "C": {"x": 70.0, "y": 32.0},
        },
        "seconds": 0.5,
        "gate": ["off", "PG"],
        "ball_owner_pos": "PG",
    }
    payload = {
        "result_type": result_type,
        "hct_bh_pos": "PG",
        "hct_bh_target": {"x": 44.0, "y": 25.0},
        "hct_other_offense_targets": {
            "SG": {"x": 58.0, "y": 18.0},
            "SF": {"x": 58.0, "y": 32.0},
            "PF": {"x": 68.0, "y": 18.0},
            "C": {"x": 68.0, "y": 32.0},
        },
        "hct_def_initial_targets": {
            "PG": {"x": 46.0, "y": 25.0},
            "SG": {"x": 56.0, "y": 18.0},
            "SF": {"x": 56.0, "y": 32.0},
            "PF": {"x": 66.0, "y": 18.0},
            "C": {"x": 66.0, "y": 32.0},
        },
        "hct_loop_segments": [segment],
    }
    if fcp:
        payload["fcp_skip_walk_up"] = True
        payload["fcp_loop_segments"] = payload.pop("hct_loop_segments")
        payload["fcp_bh_pos"] = payload.pop("hct_bh_pos")
        payload["fcp_bh_target"] = payload.pop("hct_bh_target")
        payload["fcp_other_offense_targets"] = payload.pop("hct_other_offense_targets")
        payload["fcp_def_initial_targets"] = payload.pop("hct_def_initial_targets")
    return payload


def _build_steps(payload, *, fcp=False):
    return (
        build_dynamic_fcp_animation_steps(payload, _game())
        if fcp
        else build_dynamic_hct_animation_steps(payload, _game())
    )


def _terminal_step(steps):
    return steps[-1]["end"]["next"]


def _assert_linear_or_terminal_chain(steps):
    for idx, step in enumerate(steps):
        nxt = step["end"].get("next")
        assert isinstance(nxt, dict)
        if nxt.get("kind") == "next_step":
            assert nxt.get("index") == idx + 1
        elif nxt.get("kind") == "turn_stop":
            assert idx == len(steps) - 1
        else:
            raise AssertionError(f"unexpected next pointer: {nxt}")


def _strip_pressure_state(steps):
    stripped = []
    for step in steps:
        clone = dict(step)
        clone.pop("_pressure_step_state", None)
        stripped.append(clone)
    return stripped


@pytest.mark.parametrize("fcp", [False, True])
def test_pressure_schema_chain_terminates_for_steal(fcp):
    payload = _base_payload(result_type="STEAL", reason="hct_interception", fcp=fcp)
    payload.update({"stealer_id": "def_sg", "victim_id": "off_pg", "is_interception": True})

    steps = _build_steps(payload, fcp=fcp)

    assert steps
    _assert_linear_or_terminal_chain(steps)
    assert _terminal_step(steps)["event"] == "STEAL"
    assert _terminal_step(steps)["payload"] == {
        "stealer_id": "def_sg",
        "victim_id": "off_pg",
    }


@pytest.mark.parametrize("fcp", [False, True])
def test_pressure_schema_chain_terminates_for_dead_ball(fcp):
    payload = _base_payload(result_type="DEAD BALL", reason="hct_dead_ball_turnover", fcp=fcp)
    payload.update({"victim_id": "off_pg"})

    steps = _build_steps(payload, fcp=fcp)

    assert steps
    _assert_linear_or_terminal_chain(steps)
    assert _terminal_step(steps)["event"] == "DEAD_BALL_TURNOVER"
    assert _terminal_step(steps)["payload"] == {"victim_id": "off_pg"}


@pytest.mark.parametrize("fcp", [False, True])
def test_pressure_schema_chain_terminates_for_foul(fcp):
    payload = _base_payload(result_type="FOUL", reason="hct_reach_in", fcp=fcp)
    payload.update(
        {
            "foul_team": "DEFENSE",
            "foul_player_id": "def_pg",
            "victim_id": "off_pg",
        }
    )

    steps = _build_steps(payload, fcp=fcp)

    assert steps
    _assert_linear_or_terminal_chain(steps)
    assert _terminal_step(steps)["event"] == "FOUL"
    assert _terminal_step(steps)["payload"] == {
        "foul_team": "DEFENSE",
        "fouler_id": "def_pg",
        "victim_id": "off_pg",
    }


@pytest.mark.parametrize("fcp", [False, True])
def test_pressure_normal_pass_uses_ball_reaches_player_schema(fcp):
    payload = _base_payload(result_type="HCO", reason="hct_pass", fcp=fcp)
    segment_key = "fcp_loop_segments" if fcp else "hct_loop_segments"
    payload[segment_key][0].update(
        {
            "pass_from_pos": "PG",
            "pass_to_pos": "SG",
            "ball_owner_pos": "SG",
        }
    )

    steps = _build_steps(payload, fcp=fcp)
    pass_steps = [
        step for step in steps
        if step["start"]["advance_trigger"]["condition"] == "ball_reaches_player"
    ]

    assert len(pass_steps) == 1
    trigger = pass_steps[0]["start"]["advance_trigger"]
    assert trigger["metadata"]["from_player_id"] == "off_pg"
    assert trigger["metadata"]["to_player_id"] == "off_sg"
    assert pass_steps[0]["start"]["ball"]["from_player_id"] == "off_pg"
    assert pass_steps[0]["start"]["ball"]["to_player_id"] == "off_sg"
    assert pass_steps[0]["end"]["ball"]["owner_player_id"] == "off_sg"


@pytest.mark.parametrize("fcp", [False, True])
def test_pressure_interception_emits_ball_flight_to_stealer(fcp):
    payload = _base_payload(result_type="STEAL", reason="hct_interception", fcp=fcp)
    segment_key = "fcp_loop_segments" if fcp else "hct_loop_segments"
    payload[segment_key][0].update(
        {
            "pass_from_pos": "PG",
            "pass_to_pos": "SG",
            "interceptor_pos": "SG",
            "interception_contact": {"x": 54.0, "y": 20.0},
        }
    )
    payload.update(
        {
            "stealer_id": "def_sg",
            "victim_id": "off_pg",
            "is_interception": True,
            "steal_coords": {"x": 54.0, "y": 20.0},
        }
    )

    steps = _build_steps(payload, fcp=fcp)

    assert any(
        step["start"]["advance_trigger"]["condition"] == "ball_reaches_player"
        and step["start"]["ball"].get("from_player_id") == "off_pg"
        and step["start"]["ball"].get("to_player_id") == "def_sg"
        and step["end"]["ball"].get("owner_player_id") == "def_sg"
        for step in steps
    )


@pytest.mark.parametrize("fcp", [False, True])
def test_pressure_bat_oob_emits_schema_ball_trajectory_to_oob_target(fcp):
    payload = _base_payload(result_type="DEAD BALL", reason="hct_bat_oob", fcp=fcp)
    payload.update(
        {
            "bat_oob": True,
            "bat_oob_contact": {"x": 56.0, "y": 18.0},
            "bat_oob_target": {"x": 56.0, "y": 0.0},
            "bat_oob_deflector_id": "def_sg",
        }
    )

    steps = _build_steps(payload, fcp=fcp)

    contact_steps = [
        step for step in steps
        if step["start"]["advance_trigger"]["metadata"].get("reason") == "hct_bat_oob_contact"
    ]
    drift_steps = [
        step for step in steps
        if step["start"]["advance_trigger"]["metadata"].get("reason") == "hct_bat_oob_drift"
    ]

    assert len(contact_steps) == 1
    assert len(drift_steps) == 1
    assert contact_steps[0]["start"].get("ball_motion_style") == "pass"
    assert contact_steps[0]["start"]["ball_arrival_coord"] == {"x": 56.0, "y": 18.0}
    assert contact_steps[0]["end"]["ball"].get("coords") == {"x": 56.0, "y": 18.0}
    assert contact_steps[0]["start"]["sfx_on_ball_arrival"]["event"] == "bat_oob_contact"
    assert drift_steps[0]["start"].get("ball_motion_style") == "pass"
    assert drift_steps[0]["start"]["ball"].get("coords") == {"x": 56.0, "y": 18.0}
    assert drift_steps[0]["end"]["ball"].get("coords") == {"x": 56.0, "y": 0.0}
    assert drift_steps[0]["end"]["next"]["event"] == "DEAD_BALL_TURNOVER"


@pytest.mark.parametrize("turn_type,fcp", [("HCT", False), ("FCP", True)])
def test_turn_manager_pressure_emit_stamps_schema_clock_for_non_shot(turn_type, fcp):
    payload = _base_payload(result_type="DEAD BALL", reason="hct_dead_ball_turnover", fcp=fcp)
    payload.update({"victim_id": "off_pg", "time_elapsed": 999})
    tm = TurnManager.__new__(TurnManager)
    tm.game = _game()

    tm._emit_pressure_animation_steps(payload, turn_type)

    steps = payload.get("animation_steps") or []
    assert steps
    first_clock = steps[0]["start"]["clock"]["clock_remaining"]
    last_clock = steps[-1]["end"]["clock"]["clock_remaining"]
    expected_burn = int(round(max(0.0, float(first_clock) - float(last_clock))))
    assert payload["time_elapsed"] == expected_burn
    assert payload["time_elapsed"] != 999
    assert payload["step_clock_seconds"] == [
        round(float(step["end"]["time_elapsed"] or 0.0), 2)
        for step in steps
    ]


@pytest.mark.parametrize("turn_type,fcp", [("HCT", False), ("FCP", True)])
def test_turn_manager_pressure_emit_stamps_pressure_step_state(turn_type, fcp):
    payload = _base_payload(result_type="HCO", reason="hct_pass", fcp=fcp)
    segment_key = "fcp_loop_segments" if fcp else "hct_loop_segments"
    payload[segment_key][0].update(
        {
            "pass_from_pos": "PG",
            "pass_to_pos": "SG",
            "ball_owner_pos": "SG",
        }
    )
    tm = TurnManager.__new__(TurnManager)
    tm.game = _game()

    tm._emit_pressure_animation_steps(payload, turn_type)

    steps = payload.get("animation_steps") or []
    states = payload.get("pressure_step_states") or []
    assert len(states) == len(steps)
    assert all(step.get("_pressure_step_state") == states[idx] for idx, step in enumerate(steps))

    pass_state = next(
        state for state in states
        if state["advance_gate"]["condition"] == "ball_reaches_player"
    )
    assert pass_state["turn_type"] == turn_type
    assert pass_state["ball"]["from_owner"] == "off_pg"
    assert pass_state["ball"]["to_owner"] == "off_sg"
    assert pass_state["ball"]["motion_style"] == "pass"
    assert pass_state["players"]["off_pg"]["action"] == "pass"
    assert pass_state["players"]["off_sg"]["action"] == "receive"
    assert pass_state["timing"]["step_t"] == steps[pass_state["index"]]["end"]["time_elapsed"]


@pytest.mark.parametrize("turn_type,fcp", [("HCT", False), ("FCP", True)])
def test_pressure_step_state_captures_terminal_outcome(turn_type, fcp):
    payload = _base_payload(result_type="FOUL", reason="hct_reach_in", fcp=fcp)
    payload.update(
        {
            "foul_team": "DEFENSE",
            "foul_player_id": "def_pg",
            "victim_id": "off_pg",
        }
    )
    tm = TurnManager.__new__(TurnManager)
    tm.game = _game()

    tm._emit_pressure_animation_steps(payload, turn_type)

    terminal_state = payload["pressure_step_states"][-1]
    assert terminal_state["outcome"] == {
        "kind": "foul",
        "event": "FOUL",
        "payload": {
            "foul_team": "DEFENSE",
            "fouler_id": "def_pg",
            "victim_id": "off_pg",
        },
    }


@pytest.mark.parametrize("turn_type,fcp", [("HCT", False), ("FCP", True)])
def test_pressure_step_state_captures_bat_oob_contact_and_drift(turn_type, fcp):
    payload = _base_payload(result_type="DEAD BALL", reason="hct_bat_oob", fcp=fcp)
    payload.update(
        {
            "bat_oob": True,
            "bat_oob_contact": {"x": 56.0, "y": 18.0},
            "bat_oob_target": {"x": 56.0, "y": 0.0},
            "bat_oob_deflector_id": "def_sg",
        }
    )
    tm = TurnManager.__new__(TurnManager)
    tm.game = _game()

    tm._emit_pressure_animation_steps(payload, turn_type)

    states = payload.get("pressure_step_states") or []
    contact_state = next(
        state for state in states
        if state["advance_gate"]["metadata"].get("reason") == "hct_bat_oob_contact"
    )
    drift_state = next(
        state for state in states
        if state["advance_gate"]["metadata"].get("reason") == "hct_bat_oob_drift"
    )
    assert contact_state["ball"]["contact_point"] == {"x": 56.0, "y": 18.0}
    assert contact_state["ball"]["arrival_coord"] == {"x": 56.0, "y": 18.0}
    assert drift_state["ball"]["from_coord"] == {"x": 56.0, "y": 18.0}
    assert drift_state["ball"]["end_coord"] == {"x": 56.0, "y": 0.0}
    assert drift_state["outcome"]["kind"] == "dead_ball_turnover"


@pytest.mark.parametrize(
    "turn_type,fcp,result_type,reason",
    [
        ("HCT", False, "HCO", "hct_pass"),
        ("FCP", True, "HCO", "hct_pass"),
        ("HCT", False, "STEAL", "hct_interception"),
        ("FCP", True, "STEAL", "hct_interception"),
        ("HCT", False, "DEAD BALL", "hct_bat_oob"),
        ("FCP", True, "DEAD BALL", "hct_bat_oob"),
    ],
)
def test_pressure_step_state_projection_preserves_emitted_schema(
    turn_type, fcp, result_type, reason
):
    payload = _base_payload(result_type=result_type, reason=reason, fcp=fcp)
    segment_key = "fcp_loop_segments" if fcp else "hct_loop_segments"
    if reason == "hct_pass":
        payload[segment_key][0].update(
            {
                "pass_from_pos": "PG",
                "pass_to_pos": "SG",
                "ball_owner_pos": "SG",
            }
        )
    elif reason == "hct_interception":
        payload[segment_key][0].update(
            {
                "pass_from_pos": "PG",
                "pass_to_pos": "SG",
                "interceptor_pos": "SG",
                "interception_contact": {"x": 54.0, "y": 20.0},
            }
        )
        payload.update(
            {
                "stealer_id": "def_sg",
                "victim_id": "off_pg",
                "is_interception": True,
                "steal_coords": {"x": 54.0, "y": 20.0},
            }
        )
    elif reason == "hct_bat_oob":
        payload.update(
            {
                "bat_oob": True,
                "bat_oob_contact": {"x": 56.0, "y": 18.0},
                "bat_oob_target": {"x": 56.0, "y": 0.0},
                "bat_oob_deflector_id": "def_sg",
            }
        )

    steps = _build_steps(payload, fcp=fcp)
    payload["animation_steps"] = steps

    states = build_pressure_step_states(payload, turn_type)
    projected = project_pressure_step_states_to_animation_steps(states)

    assert any(state.get("projection_source") == "formal" for state in states)
    assert _strip_pressure_state(projected) == _strip_pressure_state(steps)


@pytest.mark.parametrize("fcp", [False, True])
def test_pressure_emitter_projects_first_slice_steps_through_step_state(fcp):
    payload = _base_payload(result_type="HCO", reason="hct_pass", fcp=fcp)
    segment_key = "fcp_loop_segments" if fcp else "hct_loop_segments"
    payload[segment_key][0].update(
        {
            "pass_from_pos": "PG",
            "pass_to_pos": "SG",
            "ball_owner_pos": "SG",
        }
    )

    steps = _build_steps(payload, fcp=fcp)

    assert steps
    assert all(step.get("_pressure_step_state") for step in steps)
    assert all(
        step["_pressure_step_state"].get("projection_source") == "formal"
        for step in steps
    )


@pytest.mark.parametrize(
    "result_type,reason",
    [
        ("FOUL", "hct_reach_in"),
        ("DEAD BALL", "hct_dead_ball_turnover"),
        ("STEAL", "hct_steal"),
    ],
)
@pytest.mark.parametrize("fcp", [False, True])
def test_pressure_emitter_projects_terminal_loop_steps_through_step_state(
    fcp, result_type, reason
):
    payload = _base_payload(result_type=result_type, reason=reason, fcp=fcp)
    if result_type == "FOUL":
        payload.update(
            {
                "foul_team": "DEFENSE",
                "foul_player_id": "def_pg",
                "victim_id": "off_pg",
            }
        )
    elif result_type == "DEAD BALL":
        payload.update({"victim_id": "off_pg"})
    elif result_type == "STEAL":
        payload.update(
            {
                "stealer_id": "def_pg",
                "victim_id": "off_pg",
            }
        )

    steps = _build_steps(payload, fcp=fcp)

    assert steps
    terminal = steps[-1]
    assert terminal.get("_pressure_step_state")
    assert terminal["_pressure_step_state"].get("projection_source") == "formal"
    assert terminal["_pressure_step_state"]["outcome"]["kind"] in {
        "foul",
        "dead_ball_turnover",
        "steal",
    }
