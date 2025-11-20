"""
Tests for assist tracking in HCO instances.
Verifies that assists are correctly identified based on:
1. Last pass to shooter
2. Pass within 5 steps of shot
3. Pass went to shooter
"""

from tests.test_utils import build_mock_game
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.constants import ACTIONS


def test_assist_tracking_with_pass_to_shooter():
    """Test that assist is correctly identified when there's a pass to the shooter within 5 steps."""
    game = build_mock_game()
    tm = TurnManager(game)
    
    # Create a skeleton with a pass to shooter in the last 3 steps
    steps = [
        {
            "timestamp": 0,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "key"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
            },
            "events": []
        },
        {
            "timestamp": 300,
            "pos_actions": {
                "PG": {"action": ACTIONS["PASS"], "spot": "key"},
                "SG": {"action": ACTIONS["RECEIVE"], "spot": "upper wing"},
            },
            "events": [{"type": "pass", "from": "PG", "to": "SG"}]
        },
        {
            "timestamp": 600,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "key"},
                "SG": {"action": ACTIONS["SHOOT"], "spot": "upper wing"},
            },
            "events": [{"type": "shot", "by": "SG"}]
        }
    ]
    
    # Test derive_roles_from_steps
    derived = tm.assign_roles(skeleton={"steps": steps})
    
    # The passer should be identified (PG passed to SG, who is shooting)
    assert derived["passer"] is not None, "Passer should be identified"
    assert derived["passer"] == game.offense_team.lineup["PG"], "Passer should be PG"
    assert derived["shooter"] == game.offense_team.lineup["SG"], "Shooter should be SG"


def test_assist_tracking_pass_too_far_from_shot():
    """Test that assist is NOT identified when pass is more than 5 steps from shot."""
    game = build_mock_game()
    tm = TurnManager(game)
    
    # Create a skeleton with a pass more than 5 steps before the shot
    steps = []
    
    # Add 7 steps before the shot (pass on step 0, shot on step 6)
    for i in range(7):
        if i == 0:
            # Pass step
            steps.append({
                "timestamp": i * 300,
                "pos_actions": {
                    "PG": {"action": ACTIONS["PASS"], "spot": "key"},
                    "SG": {"action": ACTIONS["RECEIVE"], "spot": "upper wing"},
                },
                "events": [{"type": "pass", "from": "PG", "to": "SG"}]
            })
        elif i == 6:
            # Shot step
            steps.append({
                "timestamp": i * 300,
                "pos_actions": {
                    "PG": {"action": ACTIONS["DRIFT"], "spot": "key"},
                    "SG": {"action": ACTIONS["SHOOT"], "spot": "upper wing"},
                },
                "events": [{"type": "shot", "by": "SG"}]
            })
        else:
            # Intermediate steps
            steps.append({
                "timestamp": i * 300,
                "pos_actions": {
                    "PG": {"action": ACTIONS["DRIFT"], "spot": "key"},
                    "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                },
                "events": []
            })
    
    # Test derive_roles_from_steps
    derived = tm.assign_roles(skeleton={"steps": steps})
    
    # The passer should NOT be identified (pass is 6 steps from shot, > 5)
    assert derived["passer"] is None, "Passer should NOT be identified (pass too far from shot)"


def test_assist_tracking_pass_to_different_player():
    """Test that assist is NOT identified when pass goes to different player than shooter."""
    game = build_mock_game()
    tm = TurnManager(game)
    
    # Create a skeleton with a pass to a different player (not the shooter)
    steps = [
        {
            "timestamp": 0,
            "pos_actions": {
                "PG": {"action": ACTIONS["PASS"], "spot": "key"},
                "SG": {"action": ACTIONS["RECEIVE"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "lower wing"},
            },
            "events": [{"type": "pass", "from": "PG", "to": "SG"}]
        },
        {
            "timestamp": 300,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "key"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["SHOOT"], "spot": "lower wing"},
            },
            "events": [{"type": "shot", "by": "SF"}]
        }
    ]
    
    # Test derive_roles_from_steps
    derived = tm.assign_roles(skeleton={"steps": steps})
    
    # The passer should NOT be identified (PG passed to SG, but SF is shooting)
    assert derived["passer"] is None, "Passer should NOT be identified (pass didn't go to shooter)"
    assert derived["shooter"] == game.offense_team.lineup["SF"], "Shooter should be SF"


def test_assist_recorded_on_made_shot():
    """Test that assist stat is recorded when shot is made."""
    game = build_mock_game()
    sm = ShotManager(game)
    
    # Set up roles with a passer
    roles = {
        "shooter": game.offense_team.lineup["SG"],
        "passer": game.offense_team.lineup["PG"],
        "screener": game.offense_team.lineup["PF"],
        "defender": game.defense_team.lineup["PG"],
        "steps": []
    }
    
    # Record initial AST stat
    initial_ast = roles["passer"].stats["game"].get("AST", 0)
    
    # Make the shot score very high to ensure it's made
    roles["passer"].attributes["SC"] = 100
    roles["shooter"].attributes["SC"] = 100
    
    # Mock a high shot score by setting attributes
    result = sm.resolve_shot(roles)
    
    # If shot is made, AST should be recorded
    if result.get("result_type") == "MAKE":
        final_ast = roles["passer"].stats["game"].get("AST", 0)
        assert final_ast == initial_ast + 1, f"AST should increment by 1. Initial: {initial_ast}, Final: {final_ast}"
    else:
        # Shot missed - no assist recorded
        final_ast = roles["passer"].stats["game"].get("AST", 0)
        assert final_ast == initial_ast, "AST should not increment on missed shot"


def test_assist_not_recorded_when_no_passer():
    """Test that assist is NOT recorded when there's no passer."""
    game = build_mock_game()
    sm = ShotManager(game)
    
    # Set up roles WITHOUT a passer
    roles = {
        "shooter": game.offense_team.lineup["SG"],
        "passer": None,  # No passer
        "screener": game.offense_team.lineup["PF"],
        "defender": game.defense_team.lineup["PG"],
        "steps": []
    }
    
    # Make the shot score very high to ensure it's made
    roles["shooter"].attributes["SC"] = 100
    
    result = sm.resolve_shot(roles)
    
    # No AST should be recorded (no passer)
    if result.get("result_type") == "MAKE":
        # Check all players - none should have AST incremented
        for player in game.offense_team.get_all_players():
            ast = player.stats["game"].get("AST", 0)
            assert ast == 0, f"Player {player.get_name()} should not have AST: {ast}"


if __name__ == "__main__":
    # Run tests
    test_assist_tracking_with_pass_to_shooter()
    print("✓ test_assist_tracking_with_pass_to_shooter passed")
    
    test_assist_tracking_pass_too_far_from_shot()
    print("✓ test_assist_tracking_pass_too_far_from_shot passed")
    
    test_assist_tracking_pass_to_different_player()
    print("✓ test_assist_tracking_pass_to_different_player passed")
    
    test_assist_recorded_on_made_shot()
    print("✓ test_assist_recorded_on_made_shot passed")
    
    test_assist_not_recorded_when_no_passer()
    print("✓ test_assist_not_recorded_when_no_passer passed")
    
    print("\n✅ All assist tracking tests passed!")

