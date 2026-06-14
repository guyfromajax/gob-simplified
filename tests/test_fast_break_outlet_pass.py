"""
Outlet-pass role edge cases on DREB → Fast Break transitions
(`phase_resolution.resolve_fast_break_logic`):
- outlet roles stay None when the rebounder is also the ball handler
- a None `last_rebounder` is handled gracefully

Note (2026-06-12): the broader pre-refactor tests in this file (happy-path
role plumbing, steal-entry roles) were removed along with three fully-stale
FB test files after the May–Jun 2026 fast-break refactor. Current-engine FB
coverage lives in test_fast_break_rr_triangle_updates.py.
"""

import pytest
from unittest.mock import patch, MagicMock
from BackEnd.engine.phase_resolution import resolve_fast_break_logic
from BackEnd.constants.fast_break_play_types import COVERT_RELEASE
from tests.test_utils import build_mock_game


class TestFastBreakOutletPassRoles:
    """Test that outlet pass roles are correctly set on DREB → Fast Break."""
    
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

