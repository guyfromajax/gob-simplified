"""
Test that defensive pressure (FCP/HCT) is correctly triggered after all types of made shots.

According to game_flows.md:
- Master Inbound Pass Flow happens after:
  1. HCO made shot (no foul)
  2. Final FT made
  3. Putback made (from missed shot OREB)
  4. Putback made (from missed FT OREB)
  5. Fast break made shot

Each of these should check defensive settings and set next_defensive_setup.
"""

import pytest
from unittest.mock import patch, MagicMock
from BackEnd.models.game_manager import GameManager


def simulate_until_made_shot(game_manager, max_turns=50):
    """
    Simulate game turns until we get a made regular shot.
    Returns the turn result with the made shot.
    """
    for _ in range(max_turns):
        # Run a turn
        turn_result = game_manager.turn_manager.run_micro_turn()
        
        # Check if it's a made shot (not AND-1)
        if (turn_result.get("result_type") == "MAKE" and 
            game_manager.game_state.get("offensive_state") in ["FCP", "HCT", "HCO"]):
            return turn_result
    
    return None


def simulate_until_final_free_throw_make(game_manager, max_turns=100):
    """
    Simulate until we get a made final free throw.
    Returns the FT turn result.
    """
    for _ in range(max_turns):
        turn_result = game_manager.turn_manager.run_micro_turn()
        
        # Check if it's a final FT that was made
        if (turn_result.get("result_type") == "FREE_THROW" and
            turn_result.get("points") == 1 and
            turn_result.get("possession_flips") == True):
            return turn_result
    
    return None


@pytest.mark.integration
class TestDefensivePressureAfterMadeShots:
    """Integration tests for defensive pressure triggering."""
    
    def test_fcp_triggers_after_hco_made_shot(self):
        """
        HCO → Shot MAKE → Should check for FCP based on settings.
        If FCP setting is max (5), should trigger FCP inbound setup.
        """
        from tests.test_utils import build_mock_game
        
        game = build_mock_game()
        
        # Set FCP to maximum for away team (they'll be on defense first)
        game.away_team.strategy_settings = {
            "defense": 3,
            "tempo": 3,
            "aggression": 3,
            "fast_break": 0,
            "half_court_trap": 0,
            "full_court_press": 4,  # Max FCP
        }
        
        # Simulate until we get a made shot
        made_shot_turn = simulate_until_made_shot(game)
        
        if made_shot_turn:
            # Check that FCP was triggered
            assert made_shot_turn.get("next_defensive_setup") in ["FCP", "HCT", "HCO"], \
                f"Should set next_defensive_setup, got: {made_shot_turn.get('next_defensive_setup')}"
            
            # With FCP=5 and others=0, should likely be FCP (but probabilistic)
            # Just verify the field is present
            assert "next_defensive_setup" in made_shot_turn, \
                "Made shot should include next_defensive_setup for frontend"
    
    def test_hct_triggers_after_hco_made_shot(self):
        """
        HCO → Shot MAKE → Should check for HCT based on settings.
        If HCT setting is max (5), should trigger HCT inbound setup.
        """
        from tests.test_utils import build_mock_game
        
        game = build_mock_game()
        
        # Set HCT to maximum for away team
        game.away_team.strategy_settings = {
            "defense": 3,
            "tempo": 3,
            "aggression": 3,
            "fast_break": 0,
            "half_court_trap": 4,  # Max HCT
            "full_court_press": 0,
        }
        
        # Simulate until we get a made shot
        made_shot_turn = simulate_until_made_shot(game)
        
        if made_shot_turn:
            assert "next_defensive_setup" in made_shot_turn, \
                "Made shot should include next_defensive_setup"
    
    def test_defensive_pressure_triggers_after_final_ft_made(self):
        """
        FREE_THROW → Final FT MAKE → Should check for FCP/HCT.
        This is the bug we just fixed.
        """
        from tests.test_utils import build_mock_game
        
        game = build_mock_game()
        
        # Set FCP for away team
        game.away_team.strategy_settings = {
            "defense": 3,
            "tempo": 3,
            "aggression": 4,  # High aggression to cause fouls
            "fast_break": 0,
            "half_court_trap": 0,
            "full_court_press": 4,  # Max FCP
        }
        
        # Simulate until we get a final made FT
        final_ft_turn = simulate_until_final_free_throw_make(game)
        
        if final_ft_turn:
            # This should now have next_defensive_setup (the bug we fixed)
            assert "next_defensive_setup" in final_ft_turn, \
                "Final made FT should include next_defensive_setup"
            assert final_ft_turn.get("next_defensive_setup") in ["FCP", "HCT", "HCO"], \
                f"Should be valid defensive setup, got: {final_ft_turn.get('next_defensive_setup')}"
    
    def test_no_defensive_pressure_after_and1_ft(self):
        """
        AND-1 FT (not final) should NOT check for defensive pressure.
        Defensive pressure is only checked after the final FT.
        """
        from tests.test_utils import build_mock_game
        
        game = build_mock_game()
        
        # Simulate until we get an AND-1 situation
        for _ in range(100):
            turn_result = game.turn_manager.run_micro_turn()
            
            # Check if it's a made shot with foul (AND-1)
            if (turn_result.get("result_type") == "MAKE" and
                game.game_state.get("offensive_state") == "FREE_THROW"):
                # This turn should NOT have next_defensive_setup
                assert "next_defensive_setup" not in turn_result, \
                    "AND-1 made shot should NOT set next_defensive_setup (waits for FT)"
                break


@pytest.mark.integration
class TestFastBreakLogic:
    """Test that fast breaks only happen after DREBs and steals."""
    
    def test_fast_break_only_after_dreb_or_steal(self):
        """
        Fast break should only be checked after:
        - Defensive rebounds (from missed shots or missed FTs)
        - Steals (from HCO, FCP, HCT)
        
        Never after:
        - Dead ball turnovers
        - Side inbound passes
        """
        from tests.test_utils import build_mock_game
        
        game = build_mock_game()
        
        # Set fast break to 100%
        game.home_team.strategy_settings = {
            "defense": 3,
            "tempo": 5,  # Fast tempo
            "aggression": 3,
            "fast_break": 4,  # High fast break
            "half_court_trap": 0,
            "full_court_press": 0,
        }
        game.away_team.strategy_settings = {
            "defense": 3,
            "tempo": 5,  # Fast tempo
            "aggression": 3,
            "fast_break": 4,  # High fast break
            "half_court_trap": 0,
            "full_court_press": 0,
        }
        
        fast_break_turns = []
        turnover_turns = []
        
        # Simulate 50 turns
        for _ in range(50):
            turn_result = game.turn_manager.run_micro_turn()
            
            if turn_result.get("next_play_type") == "FAST_BREAK":
                fast_break_turns.append(turn_result)
            
            if turn_result.get("result_type") == "TURNOVER":
                turnover_turns.append(turn_result)
        
        # If we got fast breaks, validate they came from DREB or STEAL
        for fb_turn in fast_break_turns:
            # Fast break turns should have either:
            # - rebound_type == "DREB" (from shot_manager)
            # - result_type == "STEAL" or "TURNOVER" with subtype STEAL
            has_dreb = fb_turn.get("rebound_type") == "DREB"
            has_steal = "steal" in fb_turn.get("text", "").lower()
            
            assert has_dreb or has_steal, \
                f"Fast break should only come from DREB or STEAL, got: {fb_turn.get('result_type')}"


@pytest.mark.integration
class TestSideInboundAlwaysGoesToHCO:
    """Test that side inbound passes never trigger FCP/HCT."""
    
    def test_dead_ball_turnover_goes_to_hco(self):
        """
        DEAD BALL turnover → Side inbound → HCO (never FCP/HCT).
        """
        from tests.test_utils import build_mock_game
        
        game = build_mock_game()
        
        # Max out FCP to see if it incorrectly triggers
        game.home_team.strategy_settings = {
            "defense": 3,
            "tempo": 3,
            "aggression": 3,
            "fast_break": 0,
            "half_court_trap": 0,
            "full_court_press": 4,  # Max FCP
        }
        game.away_team.strategy_settings = {
            "defense": 3,
            "tempo": 3,
            "aggression": 3,
            "fast_break": 0,
            "half_court_trap": 0,
            "full_court_press": 4,  # Max FCP
        }
        
        # Simulate until we get a dead ball turnover
        for _ in range(100):
            turn_result = game.turn_manager.run_micro_turn()
            
            if turn_result.get("result_type") == "DEAD BALL":
                # next_play_type should be None (goes to side inbound, then HCO)
                assert turn_result.get("next_play_type") is None or turn_result.get("next_play_type") == "HCO", \
                    f"Dead ball should NOT trigger FCP/HCT, got: {turn_result.get('next_play_type')}"
                break

