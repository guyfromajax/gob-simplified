"""Final Turn pacing preflight and FLSS routing budget."""

import random
from types import SimpleNamespace

import pytest

from BackEnd.engine import phase_resolution
from BackEnd.engine.final_turn_pacing import (
    LATE_TARGET_ATTACK,
    LATE_TARGET_OUTSIDE,
    evaluate_final_turn_pacing,
)


POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _lineup(prefix):
    return {
        pos: SimpleNamespace(
            player_id=f"{prefix}_{pos}",
            attributes={"SH": 10, "SC": 10, "AG": 50, "CH": 50},
        )
        for pos in POSITIONS
    }


def _game(*, time_remaining, prior_turn=None):
    home = SimpleNamespace(team_id="home", lineup=_lineup("home"))
    away = SimpleNamespace(team_id="away", lineup=_lineup("away"))
    return SimpleNamespace(
        quarter=2,
        game_state={"time_remaining": time_remaining, "shot_clock_remaining": 14},
        home_team=home,
        away_team=away,
        offense_team=home,
        defense_team=away,
        turns=[prior_turn] if prior_turn else [],
        turn_manager=SimpleNamespace(
            assign_roles=lambda off_call, def_call, skeleton: {
                "shooter": home.lineup["PG"],
                "shooter_pos": "PG",
            }
        ),
        shot_manager=SimpleNamespace(resolve_shot=lambda roles: {"result_type": "MISS"}),
    )


def _patch_resolve(monkeypatch):
    monkeypatch.setattr(
        phase_resolution,
        "set_shooter_coords_from_skeleton_last_step",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        phase_resolution,
        "build_skeleton_pre_resolve_shot_snapshot",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        phase_resolution,
        "attach_position_snapshots",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("BackEnd.utils.situational_logic.get_score_delta", lambda game: 0)
    monkeypatch.setattr(random, "shuffle", lambda values: None)


def test_pacing_plenty_of_time_meets_anchor():
    game = _game(time_remaining=29)
    o_dest = {pos: {"x": 64 + i, "y": 25} for i, pos in enumerate(POSITIONS)}
    plan = evaluate_final_turn_pacing(
        game,
        skeleton={"steps": [{"pos_actions": {"PG": {"action": "handle_ball", "location": "deep upper wing"}}}]},
        o_destinations=o_dest,
        position_to_spot={pos: "deep upper wing" for pos in POSITIONS},
        bh_pos="PG",
        shooter_pos="PG",
        shot_type="Outside",
        bh_is_shooter=True,
        prior_turn=None,
    )
    assert plan.can_meet_anchor is True
    assert plan.step0_hold_floor > 20


def test_pacing_insufficient_time_routes_flss(monkeypatch):
    _patch_resolve(monkeypatch)
    random_values = iter([0.99, 0, 0, 0, 0, 0, 0])
    monkeypatch.setattr(random, "random", lambda: next(random_values, 0))
    monkeypatch.setattr(random, "choice", lambda values: values[0])

    game = _game(time_remaining=2)
    result = phase_resolution.resolve_final_turn_shot_logic(
        game,
        o_destinations={pos: {"x": 64, "y": 25} for pos in POSITIONS},
        d_destinations={},
        position_to_spot={pos: "deep upper wing" for pos in POSITIONS},
        bh_pos="PG",
    )
    assert result.get("route_flss") is True


def test_pacing_failure_above_legacy_cutoff_routes_flss(monkeypatch):
    _patch_resolve(monkeypatch)
    monkeypatch.setattr(random, "random", lambda: 0.99)
    monkeypatch.setattr(random, "choice", lambda values: values[0])
    monkeypatch.setattr(
        "BackEnd.engine.final_turn_pacing.evaluate_final_turn_pacing",
        lambda *args, **kwargs: SimpleNamespace(
            can_meet_anchor=False,
            reason="insufficient_total_budget",
            step0_hold_floor=0.0,
            include_entry_pass=False,
            handoff_fits=False,
            include_walkup=False,
            anchor_clock=1.0,
            micro_reserve_seconds=1.0,
        ),
    )

    game = _game(time_remaining=20)
    result = phase_resolution.resolve_final_turn_shot_logic(
        game,
        o_destinations={pos: {"x": 64, "y": 25} for pos in POSITIONS},
        d_destinations={},
        position_to_spot={pos: "deep upper wing" for pos in POSITIONS},
        bh_pos="PG",
    )

    assert result == {
        "route_flss": True,
        "flss_reason": "insufficient_total_budget",
    }


def test_pacing_hold_floor_accounts_for_move_beats(monkeypatch):
    _patch_resolve(monkeypatch)
    random_values = iter([0.01, 0, 0, 0, 0, 0, 0])
    monkeypatch.setattr(random, "random", lambda: next(random_values, 0))
    monkeypatch.setattr(random, "choice", lambda values: values[0])
    monkeypatch.setattr(random, "randint", lambda a, b: 3)

    game = _game(time_remaining=29)
    result = phase_resolution.resolve_final_turn_shot_logic(
        game,
        o_destinations={pos: {"x": 64, "y": 25} for pos in POSITIONS},
        d_destinations={},
        position_to_spot={pos: "deep upper wing" for pos in POSITIONS},
        bh_pos="PG",
    )
    assert result.get("route_flss") is not True
    floor = result["skeleton"]["steps"][0].get("_step_t_floor_game_seconds")
    assert floor is not None
    assert floor < 29 - 3


def test_pacing_does_not_omit_required_entry_pass_for_anchor():
    """When live owner != skeleton BH, never skip entry pass to salvage anchor."""
    prior = {
        "final_ball_handler_id": "home_PF",
        "final_coords": {
            f"home_{pos}": {"x": 50.0, "y": 25.0} for pos in POSITIONS
        },
    }
    game = _game(time_remaining=8, prior_turn=prior)
    o_dest = {pos: {"x": 64 + i, "y": 25} for i, pos in enumerate(POSITIONS)}
    plan = evaluate_final_turn_pacing(
        game,
        skeleton={
            "steps": [
                {"pos_actions": {"PG": {"action": "handle_ball", "location": "deep upper wing"}}},
                {"pos_actions": {"PG": {"action": "pass", "location": "deep key"}, "SG": {"action": "receive", "location": "upper wing"}}},
                {"pos_actions": {"SG": {"action": "shoot", "location": "upper wing"}}},
            ]
        },
        o_destinations=o_dest,
        position_to_spot={pos: "deep upper wing" for pos in POSITIONS},
        bh_pos="PG",
        shooter_pos="SG",
        shot_type="Outside",
        bh_is_shooter=False,
        prior_turn=prior,
    )
    assert plan.reason != "entry_pass_omitted_for_anchor"
    if plan.can_meet_anchor:
        assert plan.include_entry_pass is True


def test_final_ball_handler_id_prefers_stealer_on_steal_turn():
    from BackEnd.utils.animation_step_helpers import build_final_ball_handler_id

    turn = {
        "result_type": "STEAL",
        "stealer_id": "def_sg",
        "animation_steps": [
            {
                "end": {
                    "ball": {"owner_player_id": "off_pg"},
                }
            }
        ],
    }
    assert build_final_ball_handler_id(turn) == "def_sg"


def test_can_run_final_turn_followup_with_runway():
    from BackEnd.engine.final_turn_pacing import can_run_final_turn_followup

    prior = {
        "final_coords": {
            f"home_{pos}": {"x": 64.0, "y": 25.0}
            for pos in POSITIONS
        },
        "final_ball_handler_id": "home_PG",
    }
    game = _game(time_remaining=18, prior_turn=prior)
    o_dest = {pos: {"x": 64.0, "y": 25.0} for pos in POSITIONS}
    position_to_spot = {pos: "key" for pos in POSITIONS}
    position_to_spot["PG"] = "deep upper wing"
    position_to_spot["SG"] = "deep lower wing"
    assert can_run_final_turn_followup(
        game,
        o_destinations=o_dest,
        position_to_spot=position_to_spot,
        bh_pos="PG",
        prior_turn=prior,
    ) is True


def test_can_run_final_turn_followup_without_runway():
    from BackEnd.engine.final_turn_pacing import can_run_final_turn_followup

    prior = {
        "final_coords": {
            "home_PG": {"x": 10.0, "y": 25.0},
            **{f"home_{pos}": {"x": 12.0, "y": 25.0} for pos in POSITIONS if pos != "PG"},
        },
        "final_ball_handler_id": "home_PG",
    }
    game = _game(time_remaining=3, prior_turn=prior)
    o_dest = {pos: {"x": 64.0, "y": 25.0} for pos in POSITIONS}
    position_to_spot = {pos: "key" for pos in POSITIONS}
    position_to_spot["PG"] = "deep upper wing"
    position_to_spot["SG"] = "deep lower wing"
    assert can_run_final_turn_followup(
        game,
        o_destinations=o_dest,
        position_to_spot=position_to_spot,
        bh_pos="PG",
        prior_turn=prior,
    ) is False


def test_evaluate_final_turn_pacing_reserves_micro_seconds():
    from BackEnd.engine.final_turn_pacing import evaluate_final_turn_pacing
    from BackEnd.engine.shot_micro_movements import worst_case_final_turn_micro_reserve

    prior = {
        "final_coords": {f"home_{pos}": {"x": 64.0, "y": 25.0} for pos in POSITIONS},
        "final_ball_handler_id": "home_PG",
    }
    game = _game(time_remaining=12, prior_turn=prior)
    skeleton = {
        "steps": [
            {"pos_actions": {"PG": {"action": "handle_ball", "location": "deep upper wing"}}},
            {"pos_actions": {"PG": {"action": "pass", "location": "deep key"}, "SG": {"action": "receive", "location": "upper wing"}}},
            {"pos_actions": {"SG": {"action": "shoot", "location": "upper wing"}}},
        ]
    }
    o_dest = {pos: {"x": 64.0, "y": 25.0} for pos in POSITIONS}
    plan = evaluate_final_turn_pacing(
        game,
        skeleton=skeleton,
        o_destinations=o_dest,
        position_to_spot={pos: "deep upper wing" for pos in POSITIONS},
        bh_pos="PG",
        shooter_pos="SG",
        shot_type="Outside",
        bh_is_shooter=False,
        prior_turn=prior,
        anchor_clock=2.0,
    )
    assert plan.micro_reserve_seconds == pytest.approx(
        worst_case_final_turn_micro_reserve("Outside")
    )
