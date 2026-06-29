"""Tests for miss bounce spot calculation and FLSS visual bounce helpers."""
from unittest.mock import patch

from BackEnd.engine.skeleton_step_emitter import (
    _build_post_shot_sub_steps,
    _resolve_shooter_shot_spot,
)
from BackEnd.utils.shared import (
    _bounce_variance_for_shot_distance,
    calculate_bounce_spot,
)


class _Team:
    def __init__(self, team_id, is_home=True):
        self.team_id = team_id
        self.is_home_team = is_home


class _Game:
    def __init__(self, offense_team_id="Home"):
        self.offense_team = _Team(offense_team_id, is_home=(offense_team_id == "Home"))
        self.home_team = _Team("Home", is_home=True)
        self.away_team = _Team("Away", is_home=False)


def test_bounce_variance_scales_with_distance():
    short = _bounce_variance_for_shot_distance(10)
    mid = _bounce_variance_for_shot_distance(25)
    long = _bounce_variance_for_shot_distance(50)
    assert short[1] < mid[1] < long[1]


def test_calculate_bounce_spot_uses_live_shooter_coords_and_scales_distance():
    game = _Game("Home")
    with patch("BackEnd.utils.shared.random.randint", side_effect=lambda lo, hi: hi):
        near_rim = calculate_bounce_spot(game, shooter_coords={"x": 85, "y": 25})
        midcourt = calculate_bounce_spot(game, shooter_coords={"x": 50, "y": 25})
    assert near_rim["x"] > midcourt["x"]


def test_resolve_shooter_shot_spot_falls_back_to_turn_shooter_coords():
    shoot_step = {
        "end": {
            "coords": {
                "other": {"x": 70, "y": 25},
            }
        }
    }
    turn_result = {
        "shooter_id": "pg1",
        "shooter_coords": {"x": 52, "y": 24},
    }
    spot = _resolve_shooter_shot_spot(turn_result, shoot_step, "pg1")
    assert spot == {"x": 52.0, "y": 24.0}


def test_build_post_shot_sub_steps_flss_miss_appends_bounce():
    steps = [
        {
            "start": {
                "coords": {"pg1": {"x": 52, "y": 24}},
                "action": {"pg1": "shoot"},
                "clock": {"clock_remaining": 1.0, "shot_clock_remaining": 1.0},
            },
            "end": {
                "coords": {"pg1": {"x": 52, "y": 24}},
                "clock": {"clock_remaining": 0.0, "shot_clock_remaining": 0.0},
                "next": {"kind": "turn_stop", "event": "SHOT_ATTEMPT", "payload": {}},
            },
        }
    ]
    turn_result = {
        "result_type": "MISS",
        "shooter_id": "pg1",
        "shooter_coords": {"x": 52, "y": 24},
        "ball_bounce_x": 68.0,
        "ball_bounce_y": 26.0,
        "flss": True,
    }
    before = len(steps)
    _build_post_shot_sub_steps(steps, turn_result, {}, {}, away_offense=False)
    assert len(steps) > before
    assert any(
        (s.get("start") or {}).get("advance_trigger", {}).get("metadata", {}).get("kind") == "bounce"
        for s in steps[before:]
    )
