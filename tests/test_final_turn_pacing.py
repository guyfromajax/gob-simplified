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


def test_pacing_hold_floor_accounts_for_move_beats(monkeypatch):
    _patch_resolve(monkeypatch)
    random_values = iter([0.01, 0, 0, 0, 0, 0, 0])
    monkeypatch.setattr(random, "random", lambda: next(random_values, 0))
    monkeypatch.setattr(random, "choice", lambda values: values[0])

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
    assert floor < 29 - LATE_TARGET_OUTSIDE


def test_attack_anchor_target_is_four_seconds():
    assert LATE_TARGET_ATTACK == 4.0
    assert LATE_TARGET_OUTSIDE == 3.0


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
