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
        
        _offense, _defense, tip_turn = execute_opening_tip(game)
        
        # Verify turn structure
        assert tip_turn["result_type"] == "OPENING_TIP"
        assert "winner" in tip_turn
        assert game.game_state["opening_tip_winner"] in ["home", "away"]
        assert tip_turn["possession_flips"] == False
        # The tip burns no game clock (dead ball; ledger zeroes it) — OT-audit change.
        assert tip_turn["time_elapsed"] == 0
        assert "text" in tip_turn
        assert "animations" in tip_turn
        assert len(tip_turn["animations"]) > 0


def test_opening_tip_sets_possession():
    """Opening tip assigns possession consistently with the winner. The winner is sim_rng-driven
    (opening_tip draws from sim_rng, not global random — see the module import), so this pins the
    possession MECHANISM, not a specific team, and is deterministic regardless of the draw."""
    game = build_mock_game()
    game.quarter = 1

    _offense, _defense, tip_turn = execute_opening_tip(game)

    winner = game.game_state["opening_tip_winner"]
    assert winner in ("home", "away")
    expected_offense = game.home_team if winner == "home" else game.away_team
    assert game.offense_team is expected_offense
    assert game.defense_team is not expected_offense
    assert game.offense_team is not game.defense_team


def test_opening_tip_sets_game_state():
    """Opening tip records the winner in game_state. Winner is sim_rng-driven, so this asserts it
    is set and valid — not which team (the old random.choice mock never touched sim_rng)."""
    game = build_mock_game()
    game.quarter = 1

    _offense, _defense, tip_turn = execute_opening_tip(game)

    assert game.game_state["opening_tip_winner"] in ("home", "away")


def test_opening_tip_animation_structure():
    """Test that opening tip generates proper animation data"""
    game = build_mock_game()
    game.quarter = 1
    
    _offense, _defense, tip_turn = execute_opening_tip(game)
    
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
    
    _offense, _defense, tip_turn = execute_opening_tip(game)
    
    # Text should mention a tip-off
    assert "tip" in tip_turn["text"].lower() or "jump ball" in tip_turn["text"].lower()


def test_opening_tip_ball_animation():
    """Test that ball has proper animation data"""
    game = build_mock_game()
    game.quarter = 1
    
    _offense, _defense, tip_turn = execute_opening_tip(game)
    
    # Check that ball landing coordinates are set
    assert "ball_landing_coords" in tip_turn
    assert "x" in tip_turn["ball_landing_coords"]
    assert "y" in tip_turn["ball_landing_coords"]


def test_opening_tip_player_convergence():
    """Test that non-center players converge on ball"""
    game = build_mock_game()
    game.quarter = 1
    
    _offense, _defense, tip_turn = execute_opening_tip(game)
    
    # Count CONVERGE_ON_BALL animations
    converge_count = len([anim for anim in tip_turn["animations"] if anim.get("action") == "CONVERGE_ON_BALL"])
    
    # Should have 8 non-center players (4 home + 4 away)
    assert converge_count == 8, f"Expected 8 CONVERGE_ON_BALL animations, got {converge_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

