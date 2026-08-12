"""Focused tests for the legacy skeleton stopper helper.

Dynamic FCP/HCT outcome and animation contracts live in the dynamic engine and
UESS suites. These tests retain coverage only for the still-live isolated helper.
"""

from tests.test_utils import build_mock_game
from BackEnd.engine.phase_resolution import apply_stopper_system_to_skeleton


class TestStopperSystemFunction:
    def test_stopper_system_returns_full_skeleton_for_hco(self):
        game = build_mock_game()
        skeleton = {
            "steps": [
                {"timestamp": 0, "pos_actions": {}},
                {"timestamp": 500, "pos_actions": {}},
                {"timestamp": 1000, "pos_actions": {}},
            ]
        }

        result = apply_stopper_system_to_skeleton(
            skeleton.copy(), "HCO", game.game_state
        )

        assert len(result["steps"]) == 3
        events = result["steps"][-1].get("events", [])
        stopper_events = [
            event
            for event in events
            if event.get("type")
            in ("o_foul", "d_foul", "dead_ball_turnover", "steal")
        ]
        assert stopper_events == []

    def test_stopper_system_truncates_for_o_foul(self):
        game = build_mock_game()
        skeleton = {
            "steps": [
                {"timestamp": 0, "pos_actions": {}},
                {"timestamp": 500, "pos_actions": {}},
                {"timestamp": 1000, "pos_actions": {}},
                {"timestamp": 1500, "pos_actions": {}},
            ]
        }

        result = apply_stopper_system_to_skeleton(
            skeleton.copy(), "O_FOUL", game.game_state
        )

        assert len(result["steps"]) <= len(skeleton["steps"])
        assert result["steps"][-1]["timestamp"] < skeleton["steps"][-1]["timestamp"]
        events = result["steps"][-1].get("events", [])
        assert any(event.get("type") == "o_foul" for event in events)

    def test_stopper_system_truncates_for_steal(self):
        game = build_mock_game()
        skeleton = {
            "steps": [
                {"timestamp": 0, "pos_actions": {}},
                {"timestamp": 500, "pos_actions": {}},
                {"timestamp": 1000, "pos_actions": {}},
                {"timestamp": 1500, "pos_actions": {}},
                {"timestamp": 2000, "pos_actions": {}},
            ]
        }

        result = apply_stopper_system_to_skeleton(
            skeleton.copy(), "STEAL", game.game_state
        )

        assert len(result["steps"]) <= len(skeleton["steps"])
        events = result["steps"][-1].get("events", [])
        assert any(event.get("type") == "steal" for event in events)
        assert "steal_stop_step_index" in game.game_state
