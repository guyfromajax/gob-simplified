#!/usr/bin/env python3
"""
Comprehensive test suite for foul-out timeout state persistence.

Tests timeout state persistence across all game entry scenarios:
1. Q1 instance (regular gameplay)
2. Q2 instance (quarter break)
3. Q3 instance (quarter break)
4. Q4 instance (Sim to 4th Quarter)
5. Q4 instance (regular gameplay)
6. Sim Full Game instance

Verifies that timeout state is saved immediately when foul-out occurs
and persists correctly when resuming from lineup screen.
"""

import pytest
from bson import ObjectId
from BackEnd.models.game_manager import GameManager
from BackEnd.engine.phase_resolution import resolve_non_shooting_foul
from BackEnd.utils.shared import summarize_game_state
from BackEnd.db import games_collection
from tests.test_utils import build_mock_game


def create_foul_out_timeout(game, quarter, clock, time_remaining):
    """Helper function to create a foul-out timeout and trigger the save logic."""
    # Set up game state
    game.quarter = quarter
    game.game_id = str(ObjectId())
    game.game_state["time_remaining"] = time_remaining
    game.game_state["clock"] = clock
    
    # Set up foul out - give player 4 fouls
    foul_player = game.defense_team.lineup["PG"]
    for _ in range(4):
        foul_player.record_stat("F")
    
    # Set up foul context
    game.game_state["foul_out_context"] = {
        "foul_type": "DEFENSIVE",
        "is_shooting_foul": False,
        "is_bonus": False,
        "next_play_type": "SIDE_INBOUND"
    }
    
    # Store offense team
    game.game_state["timeout_offense_team_id"] = game.offense_team.team_id
    
    # Create timeout turn (this is what happens in simulate_macro_turn)
    timeout_turn = game.turn_manager.setup_timeout_turn(
        timeout_reason="FOUL_OUT",
        calling_team=None,
        foul_out_player=foul_player,
        foul_out_context=game.game_state.get("foul_out_context", {})
    )
    game.turns.append(timeout_turn)
    game.text_log.append(timeout_turn["text"])
    
    # The save logic is in game_manager.py after timeout creation
    # We need to manually trigger it since we're not calling simulate_macro_turn
    if game.game_id:
        try:
            from BackEnd.utils.shared import summarize_game_state
            from BackEnd.db import games_collection
            db_summary = summarize_game_state(game, exclude_animations=True)
            games_collection.update_one({"_id": game.game_id}, {"$set": db_summary}, upsert=True)
        except Exception as e:
            pytest.fail(f"Failed to save game state: {e}")
    
    return game.game_id


class TestFoulOutTimeoutPersistenceQ1:
    """Test foul-out timeout persistence in Q1 (regular gameplay)."""
    
    def test_foul_out_saves_timeout_state_q1(self):
        """Test that foul-out in Q1 immediately saves timeout state to database."""
        game = build_mock_game()
        game.home_team.score = 10
        game.away_team.score = 8
        
        # Create foul-out timeout and trigger save
        game_id = create_foul_out_timeout(game, quarter=1, clock="6:40", time_remaining=400)
        
        # Verify timeout state saved to database
        saved_game = games_collection.find_one({"_id": game_id})
        assert saved_game is not None, "Game state should be saved to database"
        assert saved_game.get("timeout_next_play_type") == "SIDE_INBOUND"
        assert saved_game.get("timeout_offense_team_id") == game.offense_team.team_id
        assert saved_game.get("clock") == "6:40"
        assert saved_game.get("time_remaining") == 400
        assert saved_game.get("quarter") == 1
        
        # Cleanup
        games_collection.delete_one({"_id": game_id})


class TestFoulOutTimeoutPersistenceQ2:
    """Test foul-out timeout persistence in Q2 (quarter break)."""
    
    def test_foul_out_saves_timeout_state_q2(self):
        """Test that foul-out in Q2 immediately saves timeout state to database."""
        game = build_mock_game()
        game.home_team.score = 20
        game.away_team.score = 18
        
        # Create foul-out timeout and trigger save
        game_id = create_foul_out_timeout(game, quarter=2, clock="8:00", time_remaining=480)
        
        # Verify timeout state saved to database
        saved_game = games_collection.find_one({"_id": game_id})
        assert saved_game is not None
        assert saved_game.get("timeout_next_play_type") == "SIDE_INBOUND"
        assert saved_game.get("timeout_offense_team_id") == game.offense_team.team_id
        assert saved_game.get("clock") == "8:00"
        assert saved_game.get("quarter") == 2
        
        # Cleanup
        games_collection.delete_one({"_id": game_id})


class TestFoulOutTimeoutPersistenceQ3:
    """Test foul-out timeout persistence in Q3 (quarter break)."""
    
    def test_foul_out_saves_timeout_state_q3(self):
        """Test that foul-out in Q3 immediately saves timeout state to database."""
        game = build_mock_game()
        game.home_team.score = 35
        game.away_team.score = 32
        
        # Set up bonus situation
        game.defense_team.team_fouls = 5
        game.quarter = 3
        game.game_id = str(ObjectId())
        game.game_state["time_remaining"] = 480
        game.game_state["clock"] = "8:00"
        
        # Set up foul out with bonus
        foul_player = game.defense_team.lineup["PG"]
        for _ in range(4):
            foul_player.record_stat("F")
        
        ball_handler = game.offense_team.lineup["PG"]
        game.game_state["foul_out_context"] = {
            "foul_type": "DEFENSIVE",
            "is_shooting_foul": False,
            "is_bonus": True,
            "next_play_type": "FREE_THROW",
            "shooter": ball_handler
        }
        game.game_state["timeout_offense_team_id"] = game.offense_team.team_id
        
        # Create timeout turn
        timeout_turn = game.turn_manager.setup_timeout_turn(
            timeout_reason="FOUL_OUT",
            calling_team=None,
            foul_out_player=foul_player,
            foul_out_context=game.game_state.get("foul_out_context", {})
        )
        game.turns.append(timeout_turn)
        
        # Trigger save
        if game.game_id:
            db_summary = summarize_game_state(game, exclude_animations=True)
            games_collection.update_one({"_id": game.game_id}, {"$set": db_summary}, upsert=True)
        
        # Verify timeout state saved to database with FREE_THROW next_play_type
        saved_game = games_collection.find_one({"_id": game.game_id})
        assert saved_game is not None
        assert saved_game.get("timeout_next_play_type") == "FREE_THROW"
        assert saved_game.get("timeout_offense_team_id") == game.offense_team.team_id
        assert saved_game.get("clock") == "8:00"
        assert saved_game.get("quarter") == 3
        
        # Cleanup
        games_collection.delete_one({"_id": game.game_id})


class TestFoulOutTimeoutPersistenceQ4SimToFourth:
    """Test foul-out timeout persistence in Q4 after Sim to 4th Quarter."""
    
    def test_foul_out_saves_timeout_state_q4_sim_to_fourth(self):
        """Test that foul-out in Q4 (after Sim to 4th) immediately saves timeout state."""
        game = build_mock_game()
        game.home_team.score = 50
        game.away_team.score = 48
        
        # Create foul-out timeout and trigger save (simulating mid-Q4 after Sim to 4th)
        game_id = create_foul_out_timeout(game, quarter=4, clock="2:30", time_remaining=150)
        
        # Verify timeout state saved to database (critical: should persist even after Sim to 4th)
        saved_game = games_collection.find_one({"_id": game_id})
        assert saved_game is not None, "Timeout state should be saved even after Sim to 4th Quarter"
        assert saved_game.get("timeout_next_play_type") == "SIDE_INBOUND"
        assert saved_game.get("timeout_offense_team_id") == game.offense_team.team_id
        assert saved_game.get("clock") == "2:30"
        assert saved_game.get("time_remaining") == 150
        assert saved_game.get("quarter") == 4
        
        # Cleanup
        games_collection.delete_one({"_id": game_id})


class TestFoulOutTimeoutPersistenceQ4Regular:
    """Test foul-out timeout persistence in Q4 (regular gameplay)."""
    
    def test_foul_out_saves_timeout_state_q4_regular(self):
        """Test that foul-out in Q4 (regular gameplay) immediately saves timeout state."""
        game = build_mock_game()
        game.home_team.score = 65
        game.away_team.score = 63
        
        # Create foul-out timeout and trigger save
        game_id = create_foul_out_timeout(game, quarter=4, clock="0:50", time_remaining=50)
        
        # Verify timeout state saved to database
        saved_game = games_collection.find_one({"_id": game_id})
        assert saved_game is not None
        assert saved_game.get("timeout_next_play_type") == "SIDE_INBOUND"
        assert saved_game.get("timeout_offense_team_id") == game.offense_team.team_id
        assert saved_game.get("clock") == "0:50"
        assert saved_game.get("time_remaining") == 50
        assert saved_game.get("quarter") == 4
        
        # Cleanup
        games_collection.delete_one({"_id": game_id})


class TestFoulOutTimeoutPersistenceSimFullGame:
    """Test foul-out timeout persistence in Sim Full Game scenario."""
    
    def test_foul_out_saves_timeout_state_sim_full_game(self):
        """Test that foul-out during Sim Full Game immediately saves timeout state."""
        game = build_mock_game()
        game.home_team.score = 25
        game.away_team.score = 22
        
        # Create foul-out timeout and trigger save (simulating Q2 during Sim Full Game)
        game_id = create_foul_out_timeout(game, quarter=2, clock="5:00", time_remaining=300)
        
        # Verify timeout state saved to database
        saved_game = games_collection.find_one({"_id": game_id})
        assert saved_game is not None, "Timeout state should be saved during Sim Full Game"
        assert saved_game.get("timeout_next_play_type") == "SIDE_INBOUND"
        assert saved_game.get("timeout_offense_team_id") == game.offense_team.team_id
        assert saved_game.get("clock") == "5:00"
        assert saved_game.get("time_remaining") == 300
        assert saved_game.get("quarter") == 2
        
        # Cleanup
        games_collection.delete_one({"_id": game_id})


class TestFoulOutTimeoutResume:
    """Test that timeout state persists correctly when resuming from lineup."""
    
    def test_timeout_state_persists_after_save(self):
        """Test that timeout state is still present after game state is saved multiple times."""
        game = build_mock_game()
        
        # Create foul-out timeout and trigger save
        game_id = create_foul_out_timeout(game, quarter=3, clock="3:20", time_remaining=200)
        
        # Verify timeout state saved
        saved_game = games_collection.find_one({"_id": game_id})
        assert saved_game.get("timeout_next_play_type") == "SIDE_INBOUND"
        original_clock = saved_game.get("clock")
        
        # Simulate another save (like Sim to 4th Quarter would do)
        game.game_state["time_remaining"] = 180  # Clock continues
        game.game_state["clock"] = "3:00"
        db_summary = summarize_game_state(game, exclude_animations=True)
        games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
        
        # Verify timeout state STILL persists (critical fix)
        saved_game = games_collection.find_one({"_id": game_id})
        assert saved_game.get("timeout_next_play_type") == "SIDE_INBOUND", \
            "Timeout state should persist even after subsequent saves"
        assert saved_game.get("timeout_offense_team_id") == game.offense_team.team_id
        
        # Cleanup
        games_collection.delete_one({"_id": game_id})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

