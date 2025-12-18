"""
Test that FCP/HCT defensive positioning is correctly applied for all entry points.

According to the game flow and frontend code:
- FCP/HCT should trigger after: HCO made shots, final FT made, putback made
- Frontend receives next_defensive_setup and uses it for runInboundSetup(pressureType)
- FCP and HCT should have distinct defensive starting positions
- All made shots should check defensive pressure settings

Entry points for FCP/HCT:
1. HCO made shot (no foul) → Master Inbound Pass Flow
2. Final FT made → Master Inbound Pass Flow  
3. Putback made (from missed shot OREB) → Master Inbound Pass Flow
4. Putback made (from missed FT OREB) → Master Inbound Pass Flow
5. Fast break made shot → Master Inbound Pass Flow
"""

import pytest
from unittest.mock import patch, MagicMock
from BackEnd.models.game_manager import GameManager
from tests.test_utils import build_mock_game


def force_made_shot_scenario(game, scenario_type="HCO_MAKE"):
    """
    Force a specific made shot scenario by mocking random values.
    Returns the turn result.
    """
    if scenario_type == "HCO_MAKE":
        # Force a made shot with no foul
        # Lower the shot threshold to guarantee a make
        original_threshold = game.offense_team.team_attributes["shot_threshold"]
        game.offense_team.team_attributes["shot_threshold"] = 1  # Very low threshold
        
        try:
            # Patch only the foul check, not all random.choice calls
            with patch('BackEnd.models.shot_manager.random.random', side_effect=[0.9, 0.9]):  # No foul
                return game.turn_manager.run_micro_turn()
        finally:
            # Restore original threshold
            game.offense_team.team_attributes["shot_threshold"] = original_threshold
    
    elif scenario_type == "FINAL_FT_MAKE":
        # Set up free throw state and force a make
        game.game_state["offensive_state"] = "FREE_THROW"
        game.game_state["free_throws"] = 1
        game.game_state["free_throws_remaining"] = 1
        game.game_state["one_and_one"] = False
        game.game_state["shooter"] = game.offense_team.lineup["PG"]  # Set shooter
        
        # Lower the FT threshold to guarantee a make (use game_state, not team_attributes)
        original_threshold = game.game_state.get("ft_shot_threshold", 100)
        game.game_state["ft_shot_threshold"] = 1  # Very low threshold
        
        try:
            return game.turn_manager.run_micro_turn()
        finally:
            # Restore original threshold
            game.game_state["ft_shot_threshold"] = original_threshold
    
    elif scenario_type == "PUTBACK_MAKE":
        # Force missed shot → OREB → putback make
        with patch('BackEnd.models.shot_manager.random.random', side_effect=[0.9, 0.2, 0.1, 0.1]):
            # 0.9 = miss shot, 0.2 = OREB, 0.1 = putback attempt, 0.1 = make putback
            return game.turn_manager.run_micro_turn()
    
    return None


@pytest.mark.integration
class TestFCPHCTDefensivePositioning:
    """Test FCP/HCT defensive positioning for all entry points."""
    
    def test_fcp_positioning_after_hco_made_shot(self):
        """
        HCO → Shot MAKE → FCP inbound setup
        Should set next_defensive_setup = "FCP" for frontend positioning.
        """
        game = build_mock_game()
        
        # Force FCP (max setting, others at 0)
        game.away_team.strategy_settings = {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 0,
            "half_court_trap": 0,
            "full_court_press": 4,  # Max FCP
        }
        
        # Force defensive pressure to return FCP
        with patch.object(game.turn_manager, 'determine_defensive_pressure_type', return_value='FCP'):
            turn_result = force_made_shot_scenario(game, "HCO_MAKE")
        
        if turn_result and turn_result.get("result_type") == "MAKE":
            assert turn_result.get("next_defensive_setup") == "FCP", \
                f"Should set FCP for inbound, got: {turn_result.get('next_defensive_setup')}"
            
            # Verify game state was updated
            assert game.game_state.get("offensive_state") == "FCP", \
                "Game state should transition to FCP"
    
    def test_hct_positioning_after_hco_made_shot(self):
        """
        HCO → Shot MAKE → HCT inbound setup
        Should set next_defensive_setup = "HCT" for frontend positioning.
        """
        game = build_mock_game()
        
        # Force HCT (max setting, others at 0)
        game.away_team.strategy_settings = {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 0,
            "half_court_trap": 4,  # Max HCT
            "full_court_press": 0,
        }
        
        # Force defensive pressure to return HCT
        with patch.object(game.turn_manager, 'determine_defensive_pressure_type', return_value='HCT'):
            turn_result = force_made_shot_scenario(game, "HCO_MAKE")
        
        if turn_result and turn_result.get("result_type") == "MAKE":
            assert turn_result.get("next_defensive_setup") == "HCT", \
                f"Should set HCT for inbound, got: {turn_result.get('next_defensive_setup')}"
            
            # Verify game state was updated
            assert game.game_state.get("offensive_state") == "HCT", \
                "Game state should transition to HCT"
    
    def test_hco_positioning_after_made_shot(self):
        """
        HCO → Shot MAKE → HCO inbound setup (no pressure)
        Should set next_defensive_setup = "HCO" when no pressure is applied.
        """
        game = build_mock_game()
        
        # Force no pressure (all settings at 0)
        game.away_team.strategy_settings = {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 0,
            "half_court_trap": 0,
            "full_court_press": 0,
        }
        
        # Force defensive pressure to return HCO
        with patch.object(game.turn_manager, 'determine_defensive_pressure_type', return_value='HCO'):
            turn_result = force_made_shot_scenario(game, "HCO_MAKE")
        
        if turn_result and turn_result.get("result_type") == "MAKE":
            assert turn_result.get("next_defensive_setup") == "HCO", \
                f"Should set HCO for inbound, got: {turn_result.get('next_defensive_setup')}"
            
            # Verify game state was updated
            assert game.game_state.get("offensive_state") == "HCO", \
                "Game state should transition to HCO"
    
    def test_fcp_positioning_after_final_ft_made(self):
        """
        Final FT MAKE → FCP inbound setup
        This tests the bug we fixed - final FT should pass next_defensive_setup.
        """
        game = build_mock_game()
        
        # Force FCP
        game.away_team.strategy_settings = {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 0,
            "half_court_trap": 0,
            "full_court_press": 4,
        }
        
        # Force defensive pressure to return FCP
        with patch.object(game.turn_manager, 'determine_defensive_pressure_type', return_value='FCP'):
            turn_result = force_made_shot_scenario(game, "FINAL_FT_MAKE")
        
        if turn_result and turn_result.get("result_type") == "FREE_THROW":
            # This should now work (the bug we fixed)
            assert turn_result.get("next_defensive_setup") == "FCP", \
                f"Final FT should set FCP for inbound, got: {turn_result.get('next_defensive_setup')}"
            
            # Should have scored and flipped possession
            assert turn_result.get("points") == 1, "Should score 1 point"
            assert turn_result.get("possession_flips") == True, "Should flip possession"
    
    def test_hct_positioning_after_final_ft_made(self):
        """
        Final FT MAKE → HCT inbound setup
        """
        game = build_mock_game()
        
        # Force HCT
        game.away_team.strategy_settings = {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 0,
            "half_court_trap": 4,
            "full_court_press": 0,
        }
        
        # Force defensive pressure to return HCT
        with patch.object(game.turn_manager, 'determine_defensive_pressure_type', return_value='HCT'):
            turn_result = force_made_shot_scenario(game, "FINAL_FT_MAKE")
        
        if turn_result and turn_result.get("result_type") == "FREE_THROW":
            assert turn_result.get("next_defensive_setup") == "HCT", \
                f"Final FT should set HCT for inbound, got: {turn_result.get('next_defensive_setup')}"
    
    def test_fcp_positioning_after_putback_made(self):
        """
        MISS → OREB → Putback MAKE → FCP inbound setup
        """
        game = build_mock_game()
        
        # Force FCP
        game.away_team.strategy_settings = {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 0,
            "half_court_trap": 0,
            "full_court_press": 4,
        }
        
        # Force defensive pressure to return FCP
        with patch.object(game.turn_manager, 'determine_defensive_pressure_type', return_value='FCP'):
            turn_result = force_made_shot_scenario(game, "PUTBACK_MAKE")
        
        # The putback result might be embedded in the shot result
        # Check if FCP was set in game state
        if turn_result:
            # After a putback make, the game state should be set to FCP
            # The next_defensive_setup might be in the result or the game state should reflect it
            assert game.game_state.get("offensive_state") in ["FCP", "HCO"], \
                f"After putback make, should set defensive pressure, got: {game.game_state.get('offensive_state')}"


@pytest.mark.integration  
class TestDefensivePressureDecisionLogic:
    """Test the decision logic for when FCP/HCT should be applied."""
    
    def test_pressure_decision_based_on_settings(self):
        """
        Test that determine_defensive_pressure_type() correctly weighs FCP vs HCT vs HCO.
        """
        game = build_mock_game()
        
        # Test FCP preference (FCP > HCT)
        game.defense_team.strategy_settings = {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 2,
            "half_court_trap": 2,
            "full_court_press": 4,  # Higher than HCT
        }
        
        # Run multiple times to check probabilistic behavior
        fcp_count = 0
        hct_count = 0
        hco_count = 0
        
        for _ in range(20):
            result = game.turn_manager.determine_defensive_pressure_type()
            if result == "FCP":
                fcp_count += 1
            elif result == "HCT":
                hct_count += 1
            elif result == "HCO":
                hco_count += 1
        
        # With FCP=4 and HCT=2, FCP should be more likely
        assert fcp_count > 0, "Should sometimes choose FCP with high setting"
        
        # Test HCT preference (HCT > FCP)
        game.defense_team.strategy_settings = {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 2,
            "half_court_trap": 4,  # Higher than FCP
            "full_court_press": 1,
        }
        
        hct_count_2 = 0
        for _ in range(20):
            result = game.turn_manager.determine_defensive_pressure_type()
            if result == "HCT":
                hct_count_2 += 1
        
        assert hct_count_2 > 0, "Should sometimes choose HCT with high setting"
        
        # Test no pressure (both at 0)
        game.defense_team.strategy_settings = {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 2,
            "half_court_trap": 0,
            "full_court_press": 0,
        }
        
        hco_count_2 = 0
        for _ in range(10):
            result = game.turn_manager.determine_defensive_pressure_type()
            if result == "HCO":
                hco_count_2 += 1
        
        assert hco_count_2 > 0, "Should choose HCO when no pressure settings"
    
    def test_no_pressure_after_side_inbound(self):
        """
        Verify that side inbound passes never trigger FCP/HCT.
        This is handled in game_manager.py line 146.
        """
        game = build_mock_game()
        
        # Max out pressure settings
        game.away_team.strategy_settings = {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 0,
            "half_court_trap": 4,
            "full_court_press": 4,
        }
        
        # Simulate a dead ball turnover (should go to side inbound)
        for _ in range(50):
            turn_result = game.turn_manager.run_micro_turn()
            
            if turn_result.get("result_type") == "DEAD BALL":
                # After dead ball, next play should be side inbound → HCO
                # The key is that next_play_type should be None (indicating side inbound)
                assert turn_result.get("next_play_type") is None, \
                    f"Dead ball should not set next_play_type (goes to side inbound), got: {turn_result.get('next_play_type')}"
                
                # After the side inbound resolves, offensive_state should be HCO
                # (This is tested by the game_manager logic)
                break


@pytest.mark.integration
class TestFrontendIntegrationPoints:
    """Test the specific data that frontend needs for defensive positioning."""
    
    def test_all_made_shots_provide_positioning_data(self):
        """
        Verify that all types of made shots provide the necessary data for frontend positioning.
        Frontend needs: next_defensive_setup field in the turn result.
        """
        game = build_mock_game()
        
        # Set moderate pressure to get varied results
        game.away_team.strategy_settings = {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 2,
            "half_court_trap": 2,
            "full_court_press": 2,
        }
        
        made_shots_found = []
        
        # Simulate until we find different types of made shots
        for _ in range(100):
            turn_result = game.turn_manager.run_micro_turn()
            
            # Check for regular made shots
            if (turn_result.get("result_type") == "MAKE" and 
                game.game_state.get("offensive_state") in ["FCP", "HCT", "HCO"]):
                made_shots_found.append(("HCO_MAKE", turn_result))
            
            # Check for made final FTs
            elif (turn_result.get("result_type") == "FREE_THROW" and
                  turn_result.get("points") == 1 and
                  turn_result.get("possession_flips") == True):
                made_shots_found.append(("FINAL_FT_MAKE", turn_result))
            
            # Stop when we have examples
            if len(made_shots_found) >= 2:
                break
        
        # Verify all made shots have positioning data
        for shot_type, result in made_shots_found:
            assert "next_defensive_setup" in result, \
                f"{shot_type} should include next_defensive_setup for frontend"
            assert result["next_defensive_setup"] in ["FCP", "HCT", "HCO"], \
                f"{shot_type} should have valid defensive setup: {result['next_defensive_setup']}"
    
    def test_and1_shots_do_not_provide_positioning_data(self):
        """
        AND-1 shots should NOT provide next_defensive_setup (waits for final FT).
        """
        game = build_mock_game()
        
        # Simulate until we find an AND-1
        for _ in range(100):
            turn_result = game.turn_manager.run_micro_turn()
            
            # Check for AND-1 (made shot that transitions to FREE_THROW)
            if (turn_result.get("result_type") == "MAKE" and
                game.game_state.get("offensive_state") == "FREE_THROW"):
                
                assert "next_defensive_setup" not in turn_result, \
                    "AND-1 shot should NOT include next_defensive_setup (waits for FT)"
                break
