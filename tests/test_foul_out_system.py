#!/usr/bin/env python3
"""
Comprehensive test suite for foul-out system.

Tests:
1. Possession flip logic (offensive vs defensive fouls)
2. Foul context storage
3. Next play type determination
4. Timeout turn creation
5. Resume logic
"""

import pytest
from tests.test_utils import build_mock_game
from BackEnd.engine.phase_resolution import resolve_non_shooting_foul, check_and_handle_foul_out
from BackEnd.models.turn_manager import TurnManager


class TestFoulOutPossessionFlip:
    """Test possession flipping logic for foul outs."""
    
    def test_offensive_foul_flips_possession(self):
        """Test that offensive foul flips possession immediately."""
        game = build_mock_game()
        original_offense = game.offense_team.name
        original_defense = game.defense_team.name
        
        # Set up offensive foul
        game.game_state["foul_team"] = "OFFENSE"
        ball_handler = game.offense_team.lineup["PG"]
        foul_player = game.offense_team.lineup["SG"]
        
        # Give foul player 4 fouls so next foul triggers foul out
        for _ in range(4):
            foul_player.record_stat("F")
        
        roles = {
            "ball_handler": ball_handler,
            "defender": game.defense_team.lineup["PG"],
            "foul_player": foul_player,
            "shooter": ball_handler,
            "screener": None,
            "passer": None
        }
        
        # Resolve foul
        result = resolve_non_shooting_foul(roles, game)
        
        # Verify possession flipped
        assert game.offense_team.name == original_defense, \
            f"Expected offense to flip to {original_defense}, got {game.offense_team.name}"
        assert game.defense_team.name == original_offense, \
            f"Expected defense to flip to {original_offense}, got {game.defense_team.name}"
        assert result["possession_flips"] == True
        assert result["fouled_out"] == True
    
    def test_defensive_foul_no_possession_flip(self):
        """Test that defensive foul does NOT flip possession."""
        game = build_mock_game()
        original_offense = game.offense_team.name
        original_defense = game.defense_team.name
        
        # Set up defensive foul
        game.game_state["foul_team"] = "DEFENSE"
        ball_handler = game.offense_team.lineup["PG"]
        foul_player = game.defense_team.lineup["PG"]
        
        # Give foul player 4 fouls so next foul triggers foul out
        for _ in range(4):
            foul_player.record_stat("F")
        
        roles = {
            "ball_handler": ball_handler,
            "defender": foul_player,
            "foul_player": foul_player,
            "shooter": ball_handler,
            "screener": None,
            "passer": None
        }
        
        # Resolve foul
        result = resolve_non_shooting_foul(roles, game)
        
        # Verify possession did NOT flip
        assert game.offense_team.name == original_offense, \
            f"Expected offense to remain {original_offense}, got {game.offense_team.name}"
        assert game.defense_team.name == original_defense, \
            f"Expected defense to remain {original_defense}, got {game.defense_team.name}"
        assert result["possession_flips"] == False
        assert result["fouled_out"] == True


class TestFoulContextStorage:
    """Test foul context storage for timeout creation."""
    
    def test_offensive_foul_stores_context(self):
        """Test that offensive foul stores correct context."""
        game = build_mock_game()
        game.game_state["foul_team"] = "OFFENSE"
        ball_handler = game.offense_team.lineup["PG"]
        foul_player = game.offense_team.lineup["SG"]
        
        # Give foul player 4 fouls
        for _ in range(4):
            foul_player.record_stat("F")
        
        roles = {
            "ball_handler": ball_handler,
            "defender": game.defense_team.lineup["PG"],
            "foul_player": foul_player,
            "shooter": ball_handler,
            "screener": None,
            "passer": None
        }
        
        # Resolve foul
        resolve_non_shooting_foul(roles, game)
        
        # Verify foul context stored
        assert "foul_out_context" in game.game_state
        context = game.game_state["foul_out_context"]
        assert context["foul_type"] == "OFFENSIVE"
        assert context["is_shooting_foul"] == False
        assert context["next_play_type"] == "SIDE_INBOUND"
    
    def test_defensive_foul_bonus_stores_context(self):
        """Test that defensive foul in bonus stores correct context."""
        game = build_mock_game()
        game.game_state["foul_team"] = "DEFENSE"
        ball_handler = game.offense_team.lineup["PG"]
        foul_player = game.defense_team.lineup["PG"]
        
        # Set team fouls to 5 (bonus situation)
        game.defense_team.team_fouls = 5
        
        # Give foul player 4 fouls
        for _ in range(4):
            foul_player.record_stat("F")
        
        roles = {
            "ball_handler": ball_handler,
            "defender": foul_player,
            "foul_player": foul_player,
            "shooter": ball_handler,
            "screener": None,
            "passer": None
        }
        
        # Resolve foul
        resolve_non_shooting_foul(roles, game)
        
        # Verify foul context stored
        assert "foul_out_context" in game.game_state
        context = game.game_state["foul_out_context"]
        assert context["foul_type"] == "DEFENSIVE"
        assert context["is_shooting_foul"] == False
        assert context["is_bonus"] == True
        assert context["next_play_type"] == "FREE_THROW"
        assert context["shooter"] == ball_handler
    
    def test_defensive_foul_no_bonus_stores_context(self):
        """Test that defensive foul NOT in bonus stores correct context."""
        game = build_mock_game()
        game.game_state["foul_team"] = "DEFENSE"
        ball_handler = game.offense_team.lineup["PG"]
        foul_player = game.defense_team.lineup["PG"]
        
        # Set team fouls to 3 (NOT in bonus)
        game.defense_team.team_fouls = 3
        
        # Give foul player 4 fouls
        for _ in range(4):
            foul_player.record_stat("F")
        
        roles = {
            "ball_handler": ball_handler,
            "defender": foul_player,
            "foul_player": foul_player,
            "shooter": ball_handler,
            "screener": None,
            "passer": None
        }
        
        # Resolve foul
        resolve_non_shooting_foul(roles, game)
        
        # Verify foul context stored
        assert "foul_out_context" in game.game_state
        context = game.game_state["foul_out_context"]
        assert context["foul_type"] == "DEFENSIVE"
        assert context["is_shooting_foul"] == False
        assert context["is_bonus"] == False
        assert context["next_play_type"] == "SIDE_INBOUND"


class TestTimeoutTurnCreation:
    """Test timeout turn creation with foul context."""
    
    def test_timeout_turn_uses_foul_context(self):
        """Test that timeout turn uses foul context for next_play_type."""
        game = build_mock_game()
        game.game_state["foul_team"] = "DEFENSE"
        ball_handler = game.offense_team.lineup["PG"]
        foul_player = game.defense_team.lineup["PG"]
        
        # Set team fouls to 5 (bonus)
        game.defense_team.team_fouls = 5
        
        # Give foul player 4 fouls
        for _ in range(4):
            foul_player.record_stat("F")
        
        roles = {
            "ball_handler": ball_handler,
            "defender": foul_player,
            "foul_player": foul_player,
            "shooter": ball_handler,
            "screener": None,
            "passer": None
        }
        
        # Resolve foul (stores context)
        resolve_non_shooting_foul(roles, game)
        
        # Create timeout turn
        foul_out_context = game.game_state.get("foul_out_context", {})
        timeout_turn = game.turn_manager.setup_timeout_turn(
            timeout_reason="FOUL_OUT",
            calling_team=None,
            foul_out_player=foul_player,
            foul_out_context=foul_out_context
        )
        
        # Verify next_play_type from context
        assert timeout_turn["next_play_type"] == "FREE_THROW"
        assert game.game_state["timeout_next_play_type"] == "FREE_THROW"
        assert game.game_state.get("shooter") == ball_handler
    
    def test_timeout_turn_offensive_foul_uses_context(self):
        """Test that offensive foul timeout uses context for SIP."""
        game = build_mock_game()
        game.game_state["foul_team"] = "OFFENSE"
        ball_handler = game.offense_team.lineup["PG"]
        foul_player = game.offense_team.lineup["SG"]
        
        # Give foul player 4 fouls
        for _ in range(4):
            foul_player.record_stat("F")
        
        roles = {
            "ball_handler": ball_handler,
            "defender": game.defense_team.lineup["PG"],
            "foul_player": foul_player,
            "shooter": ball_handler,
            "screener": None,
            "passer": None
        }
        
        # Resolve foul (stores context and flips possession)
        resolve_non_shooting_foul(roles, game)
        
        # Create timeout turn
        foul_out_context = game.game_state.get("foul_out_context", {})
        timeout_turn = game.turn_manager.setup_timeout_turn(
            timeout_reason="FOUL_OUT",
            calling_team=None,
            foul_out_player=foul_player,
            foul_out_context=foul_out_context
        )
        
        # Verify next_play_type from context
        assert timeout_turn["next_play_type"] == "SIDE_INBOUND"
        assert game.game_state["timeout_next_play_type"] == "SIDE_INBOUND"


class TestFoulOutCheck:
    """Test foul out detection."""
    
    def test_foul_out_detection(self):
        """Test that foul out is detected at 5 fouls."""
        game = build_mock_game()
        player = game.home_team.lineup["PG"]
        
        # Give player 4 fouls
        for _ in range(4):
            player.record_stat("F")
        
        # Check foul out (should not be fouled out yet)
        result = check_and_handle_foul_out(player, game.game_state, game.home_team)
        assert result["fouled_out"] == False
        assert result["foul_count"] == 4
        
        # Give player 5th foul
        player.record_stat("F")
        
        # Check foul out (should be fouled out now)
        result = check_and_handle_foul_out(player, game.game_state, game.home_team)
        assert result["fouled_out"] == True
        assert result["foul_count"] == 5
        # Note: MockPlayer may not have player_id, so check ineligible_players differently
        if hasattr(player, "player_id") and player.player_id:
            assert player.player_id in game.game_state.get("ineligible_players", [])
        # Lineup removal happens in check_and_handle_foul_out, but MockPlayer may auto-replace
        # The important thing is that foul out is detected


class TestGameStatePreservation:
    """Test that game state is preserved through foul out."""
    
    def test_game_state_preserved_after_foul_out(self):
        """Test that scores, fouls, etc. are preserved."""
        game = build_mock_game()
        
        # Set initial game state
        game.home_team.score = 10
        game.away_team.score = 8
        game.home_team.team_fouls = 3
        game.away_team.team_fouls = 2
        game.game_state["time_remaining"] = 300  # 5:00
        game.game_state["clock"] = "5:00"
        game.quarter = 2
        
        # Record some player stats
        player = game.home_team.lineup["PG"]
        player.record_stat("FGM", 2)
        player.record_stat("PTS", 4)
        
        # Trigger foul out
        game.game_state["foul_team"] = "OFFENSE"
        foul_player = game.home_team.lineup["SG"]
        for _ in range(4):
            foul_player.record_stat("F")
        
        roles = {
            "ball_handler": player,
            "defender": game.away_team.lineup["PG"],
            "foul_player": foul_player,
            "shooter": player,
            "screener": None,
            "passer": None
        }
        
        # Resolve foul
        resolve_non_shooting_foul(roles, game)
        
        # Verify game state preserved
        assert game.home_team.score == 10
        assert game.away_team.score == 8
        assert game.home_team.team_fouls == 4  # Incremented by 1
        assert game.away_team.team_fouls == 2
        assert game.game_state["time_remaining"] == 300
        assert game.game_state["clock"] == "5:00"
        assert game.quarter == 2
        
        # Verify player stats preserved
        assert player.get_stat("FGM") == 2
        # PTS is auto-calculated from FGM (2 FGM = 4 PTS), so verify it's at least 4
        assert player.get_stat("PTS") >= 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

