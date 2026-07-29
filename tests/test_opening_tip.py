"""
Tests for opening tip logic and animation data generation
"""
import pytest
from unittest.mock import patch
from BackEnd.utils.opening_tip import execute_opening_tip, get_height_scale_value
from tests.test_utils import build_mock_game


def test_opening_tip_generates_turn():
    """Test that opening tip generates a valid turn structure"""
    game = build_mock_game()
    game.quarter = 1
    game.game_state["time_remaining"] = 480
    
    # Mock random choice to make test deterministic
    with patch('random.choice') as mock_choice:
        # Make home team win
        mock_choice.return_value = game.home_team.lineup["C"]  # home center
        
        tip_turn = execute_opening_tip(game)
        
        # Verify turn structure
        assert tip_turn["result_type"] == "OPENING_TIP"
        assert "winner" in tip_turn
        assert game.game_state["opening_tip_winner"] in ["home", "away"]
        assert tip_turn["possession_flips"] == False
        assert 2 <= tip_turn["time_elapsed"] <= 5
        assert "text" in tip_turn
        assert "animations" in tip_turn
        assert len(tip_turn["animations"]) > 0


def test_opening_tip_sets_possession():
    """Test that opening tip correctly sets team possession"""
    game = build_mock_game()
    game.quarter = 1
    
    # Mock randint to make home team always win
    with patch('random.randint') as mock_randint:
        mock_randint.return_value = 6  # Maximum roll
        
        tip_turn = execute_opening_tip(game)
        
        # Home team should win ties (same height, same roll)
        assert game.game_state["opening_tip_winner"] == "home"
        assert game.offense_team == game.home_team
        assert game.defense_team == game.away_team


def test_opening_tip_sets_game_state():
    """Test that opening tip sets opening_tip_winner in game_state"""
    game = build_mock_game()
    game.quarter = 1
    
    with patch('random.choice') as mock_choice:
        # Make away team win
        mock_choice.return_value = game.away_team.lineup["C"]
        
        tip_turn = execute_opening_tip(game)
        
        assert game.game_state["opening_tip_winner"] == "away"


def test_opening_tip_animation_structure():
    """Test that opening tip generates proper animation data"""
    game = build_mock_game()
    game.quarter = 1
    
    tip_turn = execute_opening_tip(game)
    
    # Check animations exist
    assert "animations" in tip_turn
    assert len(tip_turn["animations"]) > 0
    
    # Check for tip jump animations (should be 2 - one for each center)
    tip_jumps = [anim for anim in tip_turn["animations"] if anim.get("action") == "TIP_JUMP"]
    assert len(tip_jumps) == 2, f"Expected 2 TIP_JUMP animations, got {len(tip_jumps)}"
    
    # Check for converge animations
    converge_anims = [anim for anim in tip_turn["animations"] if anim.get("action") == "CONVERGE_ON_BALL"]
    assert len(converge_anims) == 8, f"Expected 8 CONVERGE_ON_BALL animations, got {len(converge_anims)}"
    
    # Check that all animations have required fields
    for anim in tip_turn["animations"]:
        assert "playerId" in anim
        assert "start" in anim
        assert "action" in anim


def test_get_height_scale_value():
    """Height scale calculation, re-banded +3 in. for the recalibrated
    distribution (design §11.2): thresholds shifted 83->86, 81->84, 78->81, etc."""
    # Very tall player (> 86 inches)
    assert get_height_scale_value(87) == 10
    # Tall player (84-85 inches)
    assert get_height_scale_value(84) == 9
    # New centre median (82 inches) lands mid-upper scale, as the old median did.
    assert get_height_scale_value(82) == 8
    # Mid-range height (81 inches)
    assert get_height_scale_value(81) == 7
    # Short-for-a-tipper (< 76 inches)
    assert get_height_scale_value(70) == 1


def test_opening_tip_text_generation():
    """Test that opening tip generates descriptive text"""
    game = build_mock_game()
    game.quarter = 1
    
    tip_turn = execute_opening_tip(game)
    
    # Text should mention a tip-off
    assert "tip" in tip_turn["text"].lower() or "jump ball" in tip_turn["text"].lower()


def test_opening_tip_ball_animation():
    """Test that ball has proper animation data"""
    game = build_mock_game()
    game.quarter = 1
    
    tip_turn = execute_opening_tip(game)
    
    # Check that ball landing coordinates are set
    assert "ball_landing_coords" in tip_turn
    assert "x" in tip_turn["ball_landing_coords"]
    assert "y" in tip_turn["ball_landing_coords"]


def test_opening_tip_player_convergence():
    """Test that non-center players converge on ball"""
    game = build_mock_game()
    game.quarter = 1
    
    tip_turn = execute_opening_tip(game)
    
    # Count CONVERGE_ON_BALL animations
    converge_count = len([anim for anim in tip_turn["animations"] if anim.get("action") == "CONVERGE_ON_BALL"])
    
    # Should have 8 non-center players (4 home + 4 away)
    assert converge_count == 8, f"Expected 8 CONVERGE_ON_BALL animations, got {converge_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

