"""
Integration tests for opening tip - testing backend turn data structure
that will be consumed by frontend animation
"""
import pytest
from tests.test_utils import build_mock_game
from BackEnd.utils.opening_tip import execute_opening_tip


def test_opening_tip_integration_structure():
    """Test that opening tip returns all data needed for frontend animation"""
    game = build_mock_game()
    game.quarter = 1
    
    _offense, _defense, tip_turn = execute_opening_tip(game)
    
    # Verify essential turn fields
    assert "result_type" in tip_turn
    assert tip_turn["result_type"] == "OPENING_TIP"
    assert "text" in tip_turn
    assert "animations" in tip_turn
    assert "ball_landing_coords" in tip_turn
    assert "time_elapsed" in tip_turn
    assert "possession_flips" in tip_turn
    assert "next_play_type" in tip_turn
    
    # Verify animation structure
    animations = tip_turn["animations"]
    assert isinstance(animations, list)
    assert len(animations) == 10  # 2 centers + 8 other players
    
    # Verify we have exactly 2 TIP_JUMP animations (the centers)
    tip_jumps = [a for a in animations if a.get("action") == "TIP_JUMP"]
    assert len(tip_jumps) == 2
    
    for jump_anim in tip_jumps:
        assert "playerId" in jump_anim
        assert "start" in jump_anim
        assert "jumpCoords" in jump_anim
        assert "end" in jump_anim
        assert "action" in jump_anim
        assert jump_anim["action"] == "TIP_JUMP"
        
        # Verify coordinate structure
        assert "x" in jump_anim["start"]
        assert "y" in jump_anim["start"]
        assert "x" in jump_anim["jumpCoords"]
        assert "y" in jump_anim["jumpCoords"]
        assert "x" in jump_anim["end"]
        assert "y" in jump_anim["end"]
    
    # Verify we have exactly 8 CONVERGE_ON_BALL animations (non-centers)
    converge_anims = [a for a in animations if a.get("action") == "CONVERGE_ON_BALL"]
    assert len(converge_anims) == 8
    
    for converge_anim in converge_anims:
        assert "playerId" in converge_anim
        assert "start" in converge_anim
        assert "end" in converge_anim
        assert "action" in converge_anim
        assert converge_anim["action"] == "CONVERGE_ON_BALL"
        
        # Verify coordinate structure
        assert "x" in converge_anim["start"]
        assert "y" in converge_anim["start"]
        assert "x" in converge_anim["end"]
        assert "y" in converge_anim["end"]
    
    # Verify ball landing coordinates
    ball_coords = tip_turn["ball_landing_coords"]
    assert "x" in ball_coords
    assert "y" in ball_coords
    assert isinstance(ball_coords["x"], (int, float))
    assert isinstance(ball_coords["y"], (int, float))
    
    # Ball should land somewhere in the middle third of the court
    assert 40 <= ball_coords["x"] <= 60
    assert 15 <= ball_coords["y"] <= 35


def test_opening_tip_integration_possession():
    """Test that opening tip correctly sets possession for next turn"""
    game = build_mock_game()
    game.quarter = 1
    
    initial_offense = game.offense_team
    initial_defense = game.defense_team
    
    _offense, _defense, tip_turn = execute_opening_tip(game)
    
    # Possession should be assigned to one team
    assert game.offense_team is not None
    assert game.defense_team is not None
    assert game.offense_team != game.defense_team
    
    # Winner should be stored in game state
    assert "opening_tip_winner" in game.game_state
    assert game.game_state["opening_tip_winner"] in ["home", "away"]
    
    # Next play should be HCO (half court offense)
    assert tip_turn["next_play_type"] == "HCO"
    assert game.game_state["offensive_state"] == "HCO"


def test_opening_tip_integration_player_ids():
    """Test that all player IDs in animations are valid"""
    game = build_mock_game()
    game.quarter = 1
    
    # Collect all player IDs from both teams
    all_player_ids = set()
    for player in game.home_team.lineup.values():
        all_player_ids.add(getattr(player, "player_id", str(id(player))))
    for player in game.away_team.lineup.values():
        all_player_ids.add(getattr(player, "player_id", str(id(player))))
    
    _offense, _defense, tip_turn = execute_opening_tip(game)
    
    # Verify all animation player IDs are valid
    for anim in tip_turn["animations"]:
        player_id = anim["playerId"]
        assert player_id in all_player_ids, f"Invalid player ID: {player_id}"


def test_opening_tip_integration_text_generation():
    """Test that opening tip generates readable text"""
    game = build_mock_game()
    game.quarter = 1
    
    _offense, _defense, tip_turn = execute_opening_tip(game)
    
    # Text should be a non-empty string
    assert isinstance(tip_turn["text"], str)
    assert len(tip_turn["text"]) > 0
    
    # Text should mention one of the teams
    text_lower = tip_turn["text"].lower()
    assert any(word in text_lower for word in ["lancaster", "bentley", "tip", "jump"])


def test_opening_tip_integration_no_possession_flip():
    """Test that opening tip doesn't count as a possession flip"""
    game = build_mock_game()
    game.quarter = 1
    
    _offense, _defense, tip_turn = execute_opening_tip(game)
    
    # Opening tip should not count as a possession change
    assert tip_turn["possession_flips"] == False


def test_opening_tip_integration_time_elapsed():
    """Test that opening tip has realistic time elapsed"""
    game = build_mock_game()
    game.quarter = 1
    initial_time = game.game_state["time_remaining"]
    
    _offense, _defense, tip_turn = execute_opening_tip(game)

    # OT-Task 1 (Opening_Tip_UESS_Audit.md #1): the tip burns NO game clock
    # (dead-ball; the ledger authority zeroes time_elapsed downstream). The old
    # 2-5s stamp was dead — discarded before commit but inflating real_time_
    # elapsed_ms + firing a spurious clock-reconciliation warning. Now stamped 0.
    assert tip_turn["time_elapsed"] == 0
    assert isinstance(tip_turn["time_elapsed"], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

