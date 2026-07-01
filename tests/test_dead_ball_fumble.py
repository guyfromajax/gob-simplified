"""Unit tests for dead-ball turnover fumble beat injection."""

import pytest

from BackEnd.engine.dead_ball_fumble import (
    build_dead_ball_fumble_step,
    inject_dead_ball_fumble_before_turn_stop,
    is_dead_ball_fumble_turn,
    propagate_fumble_turn_flags,
    roll_dead_ball_fumble_label,
)


def _anchor_step(bh_id: str = "bh1") -> dict:
    turn_stop = {"kind": "turn_stop", "event": "DEAD_BALL_TURNOVER", "payload": {}}
    return {
        "start": {
            "coords": {
                bh_id: {"x": 50.0, "y": 25.0},
                "d1": {"x": 48.0, "y": 24.0},
            },
            "destination": {bh_id: None, "d1": None},
            "action": {bh_id: "handle_ball", "d1": "stationary"},
            "archetype": {bh_id: "stationary", "d1": "stationary"},
            "ball": {"owner_player_id": bh_id},
            "clock": {"clock_remaining": 120.0, "shot_clock_remaining": 18.0},
            "advance_trigger": {"condition": "stationary", "T_game_seconds": 0.5},
        },
        "end": {
            "coords": {
                bh_id: {"x": 50.0, "y": 25.0},
                "d1": {"x": 48.0, "y": 24.0},
            },
            "ball": {"owner_player_id": bh_id},
            "time_elapsed": 0.5,
            "clock": {"clock_remaining": 119.5, "shot_clock_remaining": 17.5},
            "next": turn_stop,
        },
    }


class TestIsDeadBallFumbleTurn:
    def test_dead_ball_turnover_qualifies(self):
        assert is_dead_ball_fumble_turn({"result_type": "DEAD_BALL_TURNOVER"})

    def test_dead_ball_spaced_qualifies(self):
        assert is_dead_ball_fumble_turn({"result_type": "DEAD BALL"})

    def test_shot_clock_excluded(self):
        assert not is_dead_ball_fumble_turn({
            "result_type": "TURNOVER",
            "turnover_type": "SHOT_CLOCK",
        })

    def test_steal_excluded(self):
        assert not is_dead_ball_fumble_turn({
            "result_type": "STEAL",
            "stealer_id": "d1",
        })

    def test_batted_oob_excluded(self):
        assert not is_dead_ball_fumble_turn({
            "result_type": "DEAD BALL",
            "bat_oob": True,
        })


class TestRollDeadBallFumbleLabel:
    def test_fifty_fifty_travel(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.engine.dead_ball_fumble.random.random",
            lambda: 0.0,
        )
        assert roll_dead_ball_fumble_label() == "TRAVEL"

    def test_fifty_fifty_double_dribble(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.engine.dead_ball_fumble.random.random",
            lambda: 0.99,
        )
        assert roll_dead_ball_fumble_label() == "DOUBLE_DRIBBLE"


class TestInjectDeadBallFumble:
    def test_rewires_anchor_and_appends_fumble(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.engine.dead_ball_fumble.roll_dead_ball_fumble_label",
            lambda: "TRAVEL",
        )
        steps = [_anchor_step()]
        turn = {"result_type": "DEAD BALL", "victim_id": "bh1"}
        inject_dead_ball_fumble_before_turn_stop(steps, turn, away_offense=False)

        assert len(steps) == 2
        assert steps[0]["end"]["next"] == {"kind": "next_step", "index": 1}
        fumble = steps[1]
        assert fumble["start"]["advance_trigger"]["metadata"]["wall_clock_hold_ms"] == 660
        assert fumble["start"]["advance_trigger"]["T_game_seconds"] == 0.0
        assert fumble["end"]["time_elapsed"] == 0.0
        assert fumble["end"]["announcement"]["text"] == "Travel!"
        assert fumble["start"]["flourish"]["bh1"]["kind"] == "fumble"
        assert turn["turnover_type"] == "TRAVEL"
        assert turn["suppress_turn_prep_turnover_announce"] is True
        assert fumble["end"]["next"]["event"] == "DEAD_BALL_TURNOVER"

    def test_no_op_without_anchor(self):
        steps = [{
            "start": {"coords": {"bh1": {"x": 1, "y": 1}}},
            "end": {
                "coords": {"bh1": {"x": 1, "y": 1}},
                "next": {"kind": "turn_stop", "event": "STEAL"},
            },
        }]
        turn = {"result_type": "DEAD BALL", "victim_id": "bh1"}
        inject_dead_ball_fumble_before_turn_stop(steps, turn, away_offense=False)
        assert len(steps) == 1


class TestPropagateFumbleTurnFlags:
    def test_copies_suppress_and_turnover_type(self):
        source = {
            "suppress_turn_prep_turnover_announce": True,
            "turnover_type": "DOUBLE_DRIBBLE",
        }
        dest = {"result_type": "DEAD BALL"}
        propagate_fumble_turn_flags(source, dest)
        assert dest["suppress_turn_prep_turnover_announce"] is True
        assert dest["turnover_type"] == "DOUBLE_DRIBBLE"

    def test_no_op_when_source_unstamped(self):
        dest = {"result_type": "DEAD BALL"}
        propagate_fumble_turn_flags({}, dest)
        assert "suppress_turn_prep_turnover_announce" not in dest


class TestDynamicFcpFumbleFlagMerge:
    def test_merges_flags_from_emitter_copy(self, monkeypatch):
        from BackEnd.engine.dynamic_fcp_step_emitter import build_dynamic_fcp_animation_steps

        def fake_build(payload, _game):
            payload["suppress_turn_prep_turnover_announce"] = True
            payload["turnover_type"] = "TRAVEL"
            return [{"start": {"coords": {}}, "end": {"coords": {}, "next": None}}]

        monkeypatch.setattr(
            "BackEnd.engine.dynamic_hct_step_emitter.build_dynamic_hct_animation_steps",
            fake_build,
        )
        canonical = {"result_type": "DEAD BALL", "fcp_loop_segments": [{}]}
        steps = build_dynamic_fcp_animation_steps(canonical, None)
        assert steps is not None
        assert canonical["suppress_turn_prep_turnover_announce"] is True
        assert canonical["turnover_type"] == "TRAVEL"


class TestBuildDeadBallFumbleStep:
    def test_pins_clock_and_zero_elapsed(self):
        coords = {"bh1": {"x": 60.0, "y": 25.0}}
        clock = {"clock_remaining": 100.0, "shot_clock_remaining": 12.0}
        step = build_dead_ball_fumble_step(
            start_coords=coords,
            ball_handler_id="bh1",
            away_offense=True,
            clock=clock,
            turnover_label="DOUBLE_DRIBBLE",
            turn_stop_next={"kind": "turn_stop", "event": "DEAD_BALL_TURNOVER"},
        )
        assert step["end"]["time_elapsed"] == 0.0
        assert step["start"]["clock"] == clock
        assert step["end"]["clock"] == clock
        assert step["end"]["announcement"]["text"] == "Double Dribble!"
        assert step["start"]["flourish"]["bh1"]["rim_unit_x"] is not None
