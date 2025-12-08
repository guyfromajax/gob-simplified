"""
Test to verify zone defense (1-3-1) correctly positions ball handler defender
on away side of court when away team is on offense and ball handler is in lower corner.

Test validates that defender x coordinate is closer to 6 (away side) than 88 (home side).

To run this test:
1. Ensure all backend dependencies are installed (pymongo, etc.)
2. Run: python3 tests/test_zone_defense_lower_corner_away_offense.py

Or run from project root with proper PYTHONPATH:
   PYTHONPATH=. python3 tests/test_zone_defense_lower_corner_away_offense.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from BackEnd.utils.shared_defense import assign_all_zone_defenders, _get_131_zone_boundaries
    from BackEnd.utils.shared import get_away_player_coords
    from BackEnd.constants import HCO_STRING_SPOTS
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("\nThis test requires the full backend environment with dependencies installed.")
    print("Please install dependencies (pymongo, etc.) or run from the proper environment.")
    sys.exit(1)

def test_131_zone_lower_corner_away_offense():
    """
    Test 1-3-1 zone defense with ball handler in lower corner when away team is on offense.
    
    Validation: Defender x coordinate should be closer to 6 (away side) than 88 (home side).
    """
    
    # Test parameters
    is_away_offense = True
    ball_spot = "lower corner"
    aggression_level = "normal"
    
    # Get lower corner coordinates in home orientation
    lower_corner_home = HCO_STRING_SPOTS.get("lower corner", {"x": 88, "y": 6})
    
    # Convert to away orientation (as it would be in actual game)
    ball_handler_coords = get_away_player_coords(lower_corner_home)
    
    # Create offensive players list (ball handler in lower corner)
    offensive_players = [
        {
            "player_id": "bh_player",
            "coords": ball_handler_coords,
            "is_ball_handler": True,
            "spot": "lower corner"
        },
        {
            "player_id": "other_player",
            "coords": get_away_player_coords(HCO_STRING_SPOTS.get("key", {"x": 64, "y": 25})),
            "is_ball_handler": False,
            "spot": "key"
        }
    ]
    
    # Get 1-3-1 zone boundaries (with lower corner shift)
    zone_boundaries = _get_131_zone_boundaries(ball_spot, is_away_offense)
    
    # Assign zone defenders
    assignments, defender_to_offensive_player = assign_all_zone_defenders(
        zone_boundaries,
        offensive_players,
        ball_handler_coords,
        ball_spot,
        aggression_level,
        is_away_offense
    )
    
    # Find which defender is guarding the ball handler
    bh_defender_pos = None
    for def_pos, player_id in defender_to_offensive_player.items():
        if player_id == "bh_player":
            bh_defender_pos = def_pos
            break
    
    if not bh_defender_pos:
        # Fallback: check if any defender has coordinates assigned
        # In 1-3-1 zone with lower corner, C should guard it
        if "C" in assignments:
            bh_defender_pos = "C"
        else:
            # Find defender closest to ball handler
            min_dist = float('inf')
            for def_pos, coords in assignments.items():
                if coords:
                    dist = ((coords["x"] - ball_handler_coords["x"]) ** 2 + 
                           (coords["y"] - ball_handler_coords["y"]) ** 2) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        bh_defender_pos = def_pos
    
    assert bh_defender_pos is not None, "No defender assigned to guard ball handler"
    
    # Get defender coordinates (these are in HOME orientation from assign_all_zone_defenders)
    defender_coords_home = assignments[bh_defender_pos]
    
    # Convert to away orientation (as animator.py does at line 1442)
    defender_coords_away = get_away_player_coords(defender_coords_home)
    
    # Validation: Defender x should be closer to 6 (away side) than 88 (home side)
    away_side_x = 6
    home_side_x = 88
    defender_x = defender_coords_away["x"]
    
    distance_to_away = abs(defender_x - away_side_x)
    distance_to_home = abs(defender_x - home_side_x)
    
    print(f"\n{'='*80}")
    print(f"Test: 1-3-1 Zone Defense - Lower Corner (Away Offense)")
    print(f"{'='*80}")
    print(f"Ball Handler Position (away orientation): x={ball_handler_coords['x']}, y={ball_handler_coords['y']}")
    print(f"Ball Handler Position (home orientation): x={lower_corner_home['x']}, y={lower_corner_home['y']}")
    print(f"Defender Position (home orientation): x={defender_coords_home['x']}, y={defender_coords_home['y']}")
    print(f"Defender Position (away orientation): x={defender_coords_away['x']}, y={defender_coords_away['y']}")
    print(f"Defender: {bh_defender_pos}")
    print(f"\nValidation:")
    print(f"  Defender x: {defender_x}")
    print(f"  Distance to away side (x=6): {distance_to_away}")
    print(f"  Distance to home side (x=88): {distance_to_home}")
    print(f"  Closer to away side: {distance_to_away < distance_to_home}")
    print(f"{'='*80}\n")
    
    assert distance_to_away < distance_to_home, (
        f"Defender x={defender_x} is closer to home side (x=88, dist={distance_to_home}) "
        f"than away side (x=6, dist={distance_to_away}). "
        f"Defender should be on away side of court."
    )
    
    return True

def test_multiple_scenarios():
    """
    Test with multiple scenarios where ball handler is in lower corner.
    Simulates different play situations.
    """
    
    test_scenarios = [
        {
            "name": "Scenario 1: Ball handler in lower corner, single offensive player",
            "offensive_players": [
                {
                    "player_id": "bh_player",
                    "coords": get_away_player_coords(HCO_STRING_SPOTS.get("lower corner", {"x": 88, "y": 6})),
                    "is_ball_handler": True,
                    "spot": "lower corner"
                }
            ]
        },
        {
            "name": "Scenario 2: Ball handler in lower corner, multiple offensive players",
            "offensive_players": [
                {
                    "player_id": "bh_player",
                    "coords": get_away_player_coords(HCO_STRING_SPOTS.get("lower corner", {"x": 88, "y": 6})),
                    "is_ball_handler": True,
                    "spot": "lower corner"
                },
                {
                    "player_id": "other_player_1",
                    "coords": get_away_player_coords(HCO_STRING_SPOTS.get("key", {"x": 64, "y": 25})),
                    "is_ball_handler": False,
                    "spot": "key"
                },
                {
                    "player_id": "other_player_2",
                    "coords": get_away_player_coords(HCO_STRING_SPOTS.get("upper wing", {"x": 73, "y": 40})),
                    "is_ball_handler": False,
                    "spot": "upper wing"
                }
            ]
        }
    ]
    
    results = []
    
    for scenario in test_scenarios:
        print(f"\n{scenario['name']}")
        print("-" * 80)
        
        try:
            is_away_offense = True
            ball_spot = "lower corner"
            aggression_level = "normal"
            
            # Get ball handler coords
            ball_handler_coords = None
            for player in scenario["offensive_players"]:
                if player.get("is_ball_handler"):
                    ball_handler_coords = player["coords"]
                    break
            
            assert ball_handler_coords is not None, "No ball handler in scenario"
            
            # Get zone boundaries
            zone_boundaries = _get_131_zone_boundaries(ball_spot, is_away_offense)
            
            # Assign defenders
            assignments, defender_to_offensive_player = assign_all_zone_defenders(
                zone_boundaries,
                scenario["offensive_players"],
                ball_handler_coords,
                ball_spot,
                aggression_level,
                is_away_offense
            )
            
            # Find ball handler defender
            bh_defender_pos = None
            for def_pos, player_id in defender_to_offensive_player.items():
                if player_id == "bh_player":
                    bh_defender_pos = def_pos
                    break
            
            if not bh_defender_pos and "C" in assignments:
                bh_defender_pos = "C"
            
            assert bh_defender_pos is not None, f"No defender found for scenario: {scenario['name']}"
            
            # Get and convert coordinates
            defender_coords_home = assignments[bh_defender_pos]
            defender_coords_away = get_away_player_coords(defender_coords_home)
            
            # Validate
            defender_x = defender_coords_away["x"]
            distance_to_away = abs(defender_x - 6)
            distance_to_home = abs(defender_x - 88)
            
            print(f"  Defender: {bh_defender_pos}")
            print(f"  Defender x (away orientation): {defender_x}")
            print(f"  Distance to away (6): {distance_to_away}")
            print(f"  Distance to home (88): {distance_to_home}")
            print(f"  ✅ Valid: {distance_to_away < distance_to_home}")
            
            assert distance_to_away < distance_to_home, (
                f"Scenario '{scenario['name']}': Defender x={defender_x} is on wrong side"
            )
            
            results.append({"scenario": scenario['name'], "passed": True})
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results.append({"scenario": scenario['name'], "passed": False, "error": str(e)})
    
    # Summary
    print(f"\n{'='*80}")
    print("Test Summary")
    print(f"{'='*80}")
    passed = sum(1 for r in results if r.get("passed", False))
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    for result in results:
        status = "✅ PASS" if result.get("passed", False) else "❌ FAIL"
        print(f"  {status}: {result['scenario']}")
        if "error" in result:
            print(f"    Error: {result['error']}")
    
    assert passed == total, f"Only {passed}/{total} scenarios passed"
    
    return True

if __name__ == "__main__":
    print("Running zone defense lower corner tests...")
    print("=" * 80)
    
    # Test 1: Basic test
    test_131_zone_lower_corner_away_offense()
    print("✅ Test 1 passed: Basic 1-3-1 zone lower corner test")
    
    # Test 2: Multiple scenarios
    test_multiple_scenarios()
    print("✅ Test 2 passed: Multiple skeleton scenarios")
    
    print("\n" + "="*80)
    print("All tests passed! ✅")
    print("="*80)
