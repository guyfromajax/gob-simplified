"""
Test that Fast Break outlet pass roles are correctly set on DREB → Fast Break transitions.

According to phase_resolution.py resolve_fast_break_logic():
- When Fast Break is triggered from a DREB (defensive rebound):
  - `outlet_passer` should be set to the rebounder's player_id
  - `outlet_receiver` should be set to the ball_handler's player_id
  - Both should only be set if rebounder != ball_handler

This test verifies that outlet pass roles are correctly assigned.
"""

import pytest
from unittest.mock import patch, MagicMock
from BackEnd.engine.phase_resolution import resolve_fast_break_logic
from BackEnd.constants.fast_break_play_types import COVERT_RELEASE
from tests.test_utils import build_mock_game


class TestFastBreakOutletPassRoles:
    """Test that outlet pass roles are correctly set on DREB → Fast Break."""
    
    def test_outlet_pass_roles_set_on_dreb_to_fast_break(self):
        """
        Test that outlet_passer and outlet_receiver are set when Fast Break 
        is triggered from a defensive rebound.
        """
        game = build_mock_game()
        
        # Set fast break chance to 100% for testing
        game.home_team.strategy_settings["fast_break"] = 5  # Max setting
        
        # Set offense team (the team that will run the fast break after getting the DREB)
        game.offense_team = game.home_team
        game.defense_team = game.away_team
        
        # Get a rebounder from the offense team (they grabbed the DREB)
        rebounder = game.home_team.lineup["C"]  # Use center as rebounder
        rebounder.player_id = "rebounder_c_id"
        
        # Set up game state for DREB → Fast Break (Covert path; resolver uses pending key from shot turn)
        game.game_state["last_rebound"] = "DREB"
        game.game_state["last_rebounder"] = rebounder
        game.game_state["offensive_state"] = "FAST_BREAK"
        game.game_state["pending_dreb_fb_play_key"] = COVERT_RELEASE
        
        # Mock random calls to ensure predictable results
        # Ball handler is chosen from PG/SG/SF (75%/15%/10%)
        # Rebounder is C, so they should be different
        with patch('BackEnd.engine.phase_resolution.random.choices') as mock_choices, \
             patch('BackEnd.engine.phase_resolution.random.choice') as mock_choice, \
             patch('BackEnd.engine.phase_resolution.random.randint', return_value=1):
            # First call: ball_handler position selection
            # Subsequent calls: event_type determination (when d_count >= 1, returns ["SHOT"] or ["DEFENSIVE_STOP"])
            # We want SHOT to actually get through and test outlet roles in result
            mock_choices.side_effect = [
                ["PG"],  # Ball handler position
                ["SHOT"],  # Event type when d_count >= 1
            ]
            mock_choice.return_value = game.home_team.lineup["PG"]  # Shooter selection
            
            result = resolve_fast_break_logic(game)
        
        # Verify Fast Break result
        assert result is not None
        assert result.get("fast_break") is True
        assert "roles" in result
        
        roles = result["roles"]
        
        # Verify outlet pass roles are set
        assert "outlet_passer" in roles, "outlet_passer should be in roles"
        assert "outlet_receiver" in roles, "outlet_receiver should be in roles"
        assert roles["outlet_passer"] is not None, "outlet_passer should not be None"
        assert roles["outlet_receiver"] is not None, "outlet_receiver should not be None"
        
        # Verify outlet_passer is the rebounder
        assert roles["outlet_passer"] == rebounder.player_id, \
            f"outlet_passer should be rebounder's player_id ({rebounder.player_id}), got {roles['outlet_passer']}"
        
        # Verify outlet_receiver is the ball_handler
        ball_handler = roles.get("ball_handler")
        assert ball_handler is not None, "ball_handler should be set in roles"
        assert roles["outlet_receiver"] == getattr(ball_handler, "player_id", None), \
            f"outlet_receiver should be ball_handler's player_id, got {roles['outlet_receiver']}"
        
        print(f"✅ Test passed: outlet_passer={roles['outlet_passer']}, outlet_receiver={roles['outlet_receiver']}")
    
    def test_outlet_pass_roles_not_set_when_rebounder_is_ball_handler(self):
        """
        Test that outlet_passer and outlet_receiver are None when the rebounder
        is also the ball_handler (same player).
        """
        game = build_mock_game()
        
        game.offense_team = game.home_team
        game.defense_team = game.away_team
        
        # Use PG as rebounder (and it will also be ball_handler)
        rebounder = game.home_team.lineup["PG"]
        rebounder.player_id = "rebounder_pg_id"
        
        # Set up game state
        game.game_state["last_rebound"] = "DREB"
        game.game_state["last_rebounder"] = rebounder
        game.game_state["offensive_state"] = "FAST_BREAK"
        game.game_state["pending_dreb_fb_play_key"] = COVERT_RELEASE
        
        # Force ball_handler to be PG (same as rebounder)
        with patch('BackEnd.engine.phase_resolution.random.choices') as mock_choices, \
             patch('BackEnd.engine.phase_resolution.random.choice') as mock_choice, \
             patch('BackEnd.engine.phase_resolution.random.randint', return_value=1):
            mock_choices.side_effect = [
                ["PG"],  # Ball handler position (same as rebounder)
                ["SHOT"],  # Event type
            ]
            mock_choice.return_value = game.home_team.lineup["PG"]  # Shooter selection
            
            result = resolve_fast_break_logic(game)
        
        roles = result["roles"]
        
        # Verify outlet pass roles are None (since rebounder == ball_handler)
        assert roles["outlet_passer"] is None, \
            "outlet_passer should be None when rebounder == ball_handler"
        assert roles["outlet_receiver"] is None, \
            "outlet_receiver should be None when rebounder == ball_handler"
        
        print(f"✅ Test passed: outlet roles correctly None when rebounder == ball_handler")
    
    def test_outlet_pass_roles_not_set_on_steal_fast_break(self):
        """
        Test that outlet_passer and outlet_receiver are None when Fast Break
        is triggered from a steal (not a DREB).
        """
        game = build_mock_game()
        
        game.offense_team = game.home_team
        game.defense_team = game.away_team
        
        # Set up game state for STEAL → Fast Break (no last_rebound = "DREB")
        game.game_state["last_rebound"] = ""  # Not a DREB
        game.game_state["last_stealer"] = game.home_team.lineup["PG"]
        game.game_state["offensive_state"] = "FAST_BREAK"
        
        result = resolve_fast_break_logic(game)
        
        roles = result["roles"]
        
        # Verify outlet pass roles are None (steal fast breaks don't have outlet passes)
        assert roles["outlet_passer"] is None, \
            "outlet_passer should be None for steal-based fast breaks"
        assert roles["outlet_receiver"] is None, \
            "outlet_receiver should be None for steal-based fast breaks"
        
        print(f"✅ Test passed: outlet roles correctly None for steal-based fast breaks")
    
    def test_outlet_pass_roles_when_rebounder_is_none(self):
        """
        Test that outlet_passer and outlet_receiver are None when last_rebounder 
        is None (edge case).
        """
        game = build_mock_game()
        
        game.offense_team = game.home_team
        game.defense_team = game.away_team
        
        # Set up game state with DREB but no rebounder
        game.game_state["last_rebound"] = "DREB"
        game.game_state["last_rebounder"] = None  # No rebounder set
        game.game_state["offensive_state"] = "FAST_BREAK"
        game.game_state["pending_dreb_fb_play_key"] = COVERT_RELEASE
        
        # Mock to ensure we get a SHOT result (not DEFENSIVE_STOP) so we can check roles
        with patch('BackEnd.engine.phase_resolution.random.choices') as mock_choices, \
             patch('BackEnd.engine.phase_resolution.random.choice') as mock_choice, \
             patch('BackEnd.engine.phase_resolution.random.randint', return_value=1):
            mock_choices.side_effect = [
                ["PG"],  # Ball handler position
                ["SHOT"],  # Event type (force SHOT so we can check roles)
            ]
            mock_choice.return_value = game.home_team.lineup["PG"]  # Shooter selection
            
            result = resolve_fast_break_logic(game)
        
        # If result_type is DEFENSIVE_STOP, it returns early without roles
        # In that case, we can't verify outlet pass roles, but we can verify the function handled None rebounder gracefully
        if result.get("result_type") == "DEFENSIVE_STOP":
            # Early return for DEFENSIVE_STOP doesn't include roles
            # But we verified the function handled None rebounder without crashing
            assert result is not None
            print(f"✅ Test passed: function handled None rebounder gracefully (DEFENSIVE_STOP)")
        else:
            # SHOT result includes roles
            assert "roles" in result
            roles = result["roles"]
            
            # Verify outlet pass roles are None (no rebounder)
            assert roles["outlet_passer"] is None, \
                "outlet_passer should be None when last_rebounder is None"
            assert roles["outlet_receiver"] is None, \
                "outlet_receiver should be None when last_rebounder is None"
            
            print(f"✅ Test passed: outlet roles correctly None when last_rebounder is None")

