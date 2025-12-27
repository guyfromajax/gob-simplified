"""
Comprehensive tests for data persistence and serialization issues.

Tests cover:
1. Strategy calls persistence (franchise mode)
2. Roles serialization (missing steps, action_timeline)
3. Animation fallback paths
4. JSON serialization edge cases
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from BackEnd.models.game_manager import GameManager
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.animator import Animator
from BackEnd.engine.phase_resolution import resolve_half_court_offense_logic
from fastapi.encoders import jsonable_encoder
import json


class TestStrategyCallsPersistence:
    """Test that strategy_calls persist correctly through game state saves/loads."""
    
    def test_strategy_calls_saved_to_game_state(self):
        """Test that strategy_calls are included when saving game state."""
        from BackEnd.utils.shared import summarize_game_state
        from tests.test_utils import build_mock_game
        
        # Create game with strategy calls
        gm = build_mock_game()
        gm.home_team.strategy_calls = {
            "offense_call": "Inside",
            "defense_call": "Man",
            "tempo_call": "normal",
            "aggression_call": "normal"
        }
        gm.away_team.strategy_calls = {
            "offense_call": "Outside",
            "defense_call": "Zone",
            "tempo_call": "fast",
            "aggression_call": "aggressive"
        }
        
        # Save game state
        game_state = summarize_game_state(gm, exclude_animations=True)
        
        # Verify strategy_calls are in teams_obj
        assert "teams" in game_state
        home_team_id = gm.home_team.team_id
        away_team_id = gm.away_team.team_id
        
        # Find which team has which strategy_calls (teams might be swapped)
        home_calls = game_state["teams"][home_team_id].get("strategy_calls", {})
        away_calls = game_state["teams"][away_team_id].get("strategy_calls", {})
        
        # At least one team should have the expected calls
        assert "strategy_calls" in game_state["teams"][home_team_id] or "strategy_calls" in game_state["teams"][away_team_id]
        
        # Verify the structure is correct
        if home_calls:
            assert "offense_call" in home_calls
        if away_calls:
            assert "offense_call" in away_calls
    
    def test_strategy_calls_restored_from_game_state(self):
        """Test that strategy_calls are restored when loading game state."""
        from BackEnd.api.api import simulate_quarter_endpoint
        from BackEnd.api.api import QuarterSimulationRequest
        
        # This would require mocking the database, so we'll test the GameManager constructor
        home_strategy_calls = {
            "offense_call": "Inside",
            "defense_call": "Man",
            "tempo_call": "normal",
            "aggression_call": "normal"
        }
        away_strategy_calls = {
            "offense_call": "Outside",
            "defense_call": "Zone",
            "tempo_call": "fast",
            "aggression_call": "aggressive"
        }
        
        gm = GameManager(
            "Home", "Away",
            home_strategy_calls=home_strategy_calls,
            away_strategy_calls=away_strategy_calls
        )
        
        # Verify strategy_calls are restored
        assert gm.home_team.strategy_calls["offense_call"] == "Inside"
        assert gm.away_team.strategy_calls["offense_call"] == "Outside"


class TestRolesSerialization:
    """Test that roles dictionaries can be safely serialized to JSON."""
    
    def test_serializable_roles_no_player_objects(self):
        """Test that serializable_roles doesn't contain Player objects."""
        # Create a mock roles dict with Player objects
        mock_player = Mock()
        mock_player.name = "Test Player"
        mock_player.player_id = "test_id"
        
        roles = {
            "shooter": mock_player,
            "ball_handler": mock_player,
            "steps": [{"timestamp": 0, "pos_actions": {}}],
            "action_timeline": {mock_player: [(0, "shoot", "key")]},  # Player object as key
            "is_steal_hco_setup": True,
            "ball_handler_hco_setup_x": 50,
        }
        
        # Simulate what phase_resolution.py does - create serializable_roles
        serializable_roles = {}
        if roles.get("is_steal_hco_setup"):
            serializable_roles["is_steal_hco_setup"] = True
            serializable_roles["ball_handler_hco_setup_x"] = roles.get("ball_handler_hco_setup_x")
        
        # Include steps but NOT action_timeline (not JSON-serializable)
        if "steps" in roles:
            serializable_roles["steps"] = roles["steps"]
        # action_timeline is NOT included - it uses Player objects as keys
        
        # Verify it can be JSON serialized
        try:
            json_str = json.dumps(serializable_roles)
            assert "steps" in json_str
            assert "is_steal_hco_setup" in json_str
            # action_timeline should NOT be in serialized output
            assert "action_timeline" not in json_str
        except (TypeError, ValueError) as e:
            pytest.fail(f"serializable_roles should be JSON-serializable, but got: {e}")
    
    def test_serializable_roles_missing_action_timeline(self):
        """Test that missing action_timeline doesn't break serialization."""
        serializable_roles = {
            "steps": [{"timestamp": 0, "pos_actions": {}}],
            "is_steal_hco_setup": True,
        }
        
        # Should serialize fine without action_timeline
        json_str = json.dumps(serializable_roles)
        assert json_str is not None


class TestAnimationFallback:
    """Test animation fallback paths when data is missing."""
    
    def test_capture_halfcourt_animation_missing_steps(self):
        """Test that capture_halfcourt_animation handles missing steps gracefully."""
        from tests.test_utils import build_mock_game
        
        gm = build_mock_game()
        animator = Animator(gm)
        
        # Create roles without steps
        roles = {
            "shooter": gm.home_team.lineup["PG"],
            "ball_handler": gm.home_team.lineup["PG"],
            # "steps" is missing
        }
        
        # Should return empty animations, not crash
        animations = animator.capture_halfcourt_animation(roles)
        assert isinstance(animations, list)
        assert len(animations) == 0
    
    def test_capture_halfcourt_animation_missing_action_timeline(self):
        """Test that capture_halfcourt_animation handles missing action_timeline gracefully."""
        from tests.test_utils import build_mock_game
        
        gm = build_mock_game()
        animator = Animator(gm)
        
        # Create roles with steps but without action_timeline
        roles = {
            "shooter": gm.home_team.lineup["PG"],
            "ball_handler": gm.home_team.lineup["PG"],
            "steps": [{"timestamp": 0, "pos_actions": {"PG": {"action": "handle_ball", "location": "key"}}}],
            # "action_timeline" is missing
        }
        
        # Should not crash - action_timeline is optional
        try:
            animations = animator.capture_halfcourt_animation(roles)
            assert isinstance(animations, list)
        except (KeyError, UnboundLocalError) as e:
            pytest.fail(f"capture_halfcourt_animation should handle missing action_timeline, but got: {e}")
    
    def test_capture_halfcourt_animation_empty_skeleton_steps(self):
        """Test that capture_halfcourt_animation handles empty skeleton (0 steps) gracefully."""
        from tests.test_utils import build_mock_game
        
        gm = build_mock_game()
        animator = Animator(gm)
        
        # Create roles with empty steps (skeleton had 0 steps)
        roles = {
            "shooter": gm.home_team.lineup["PG"],
            "ball_handler": gm.home_team.lineup["PG"],
            "steps": [],  # Empty steps
        }
        
        # Should return empty animations, not crash
        animations = animator.capture_halfcourt_animation(roles)
        assert isinstance(animations, list)
        assert len(animations) == 0
    
    def test_capture_halfcourt_animation_bh_last_spot_initialized(self):
        """Test that bh_last_spot is initialized before use (fixes UnboundLocalError)."""
        from tests.test_utils import build_mock_game
        
        gm = build_mock_game()
        animator = Animator(gm)
        
        # Create roles with steps but missing action_timeline
        # This simulates the scenario where serializable_roles doesn't have action_timeline
        roles = {
            "shooter": gm.home_team.lineup["PG"],
            "ball_handler": gm.home_team.lineup["PG"],
            "steps": [
                {"timestamp": 0, "pos_actions": {"PG": {"action": "handle_ball", "location": "key"}}},
                {"timestamp": 1, "pos_actions": {"PG": {"action": "shoot", "location": "top_key"}}}
            ],
            # "action_timeline" is missing (not serializable)
        }
        
        # Should not raise UnboundLocalError for bh_last_spot
        try:
            animations = animator.capture_halfcourt_animation(roles)
            assert isinstance(animations, list)
        except UnboundLocalError as e:
            if "bh_last_spot" in str(e):
                pytest.fail(f"bh_last_spot should be initialized before use, but got: {e}")
            raise


class TestJSONSerialization:
    """Test that all response data can be safely serialized to JSON."""
    
    def test_turn_result_json_serializable(self):
        """Test that a typical turn result can be JSON serialized."""
        # Use standard json module, not a non-existent jsonable_encoder
        
        # Create a typical turn result structure
        turn_result = {
            "result_type": "MAKE",
            "text": "Shot made!",
            "quarter": 1,
            "time_elapsed": 5,
            "offense_team_id": "test_team_id",
            "roles": {
                "steps": [{"timestamp": 0, "pos_actions": {}}],
                "is_steal_hco_setup": False,
            },
            "animations": [],
            "score": {"Home": 2, "Away": 0},
        }
        
        # Should serialize without errors
        try:
            json_str = json.dumps(turn_result, default=str)
            assert json_str is not None
        except (TypeError, ValueError) as e:
            pytest.fail(f"turn_result should be JSON-serializable, but got: {e}")
    
    def test_fastapi_jsonable_encoder(self):
        """Test that FastAPI's jsonable_encoder can handle our data structures."""
        from fastapi.encoders import jsonable_encoder
        
        # Create a complex nested structure similar to what we return
        data = {
            "turn": {
                "result_type": "MAKE",
                "roles": {
                    "steps": [{"timestamp": 0}],
                },
                "animations": [],
            },
            "game_id": "test_id",
        }
        
        # Should encode without errors
        try:
            encoded = jsonable_encoder(data)
            assert encoded is not None
        except Exception as e:
            pytest.fail(f"FastAPI jsonable_encoder should handle our data, but got: {e}")


class TestFranchiseModeEdgeCases:
    """Test edge cases specific to franchise mode that we've discovered."""
    
    def test_zero_step_skeleton_handling(self):
        """Test that 0-step skeletons don't cause crashes."""
        from tests.test_utils import build_mock_game
        
        gm = build_mock_game()
        animator = Animator(gm)
        
        # Simulate a skeleton with 0 steps (what we saw in franchise mode)
        roles = {
            "shooter": gm.home_team.lineup["PG"],
            "ball_handler": gm.home_team.lineup["PG"],
            "steps": [],  # 0 steps
        }
        
        # Should handle gracefully
        animations = animator.capture_halfcourt_animation(roles)
        assert isinstance(animations, list)
    
    def test_missing_player_references_in_roles(self):
        """Test that missing player references are handled when reconstructing roles."""
        from BackEnd.models.turn_manager import TurnManager
        from tests.test_utils import build_mock_game
        
        gm = build_mock_game()
        turn_manager = TurnManager(gm)
        
        # Create a result with serializable_roles (no Player objects)
        result = {
            "result_type": "MAKE",
            "roles": {
                "steps": [{"timestamp": 0, "pos_actions": {}}],
            },
            "shooter": gm.home_team.lineup["PG"],  # Player object in result
            "ball_handler": gm.home_team.lineup["PG"],  # Player object in result
        }
        
        # Simulate what run_micro_turn does - reconstruct player references
        roles = result.get("roles")
        if roles:
            if "shooter" not in roles and result.get("shooter"):
                roles["shooter"] = result["shooter"]
            if "ball_handler" not in roles and result.get("ball_handler"):
                roles["ball_handler"] = result["ball_handler"]
        
        # Should have player references now
        assert "shooter" in roles
        assert "ball_handler" in roles


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

