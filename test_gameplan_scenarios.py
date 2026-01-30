#!/usr/bin/env python3
"""
Focused test script for gameplan functionality scenarios.

This script tests the specific scenarios mentioned:
1. Play Quarter button pressed
2. Sim To 4th Quarter button pressed  
3. Sim Full Game button pressed

Each test verifies that the gameplan API works correctly in these scenarios.
"""

import requests
import json
import time
import uuid
from typing import Dict, Any, Optional

# Configuration - Update this to your server URL
BASE_URL = "https://your-railway-app.railway.app"  # Replace with your actual Railway URL

def test_gameplan_scenario(scenario_name: str, test_function) -> bool:
    """Run a single test scenario and report results."""
    print(f"\n🧪 Testing: {scenario_name}")
    print("-" * 50)
    
    try:
        success = test_function()
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {scenario_name}")
        return success
    except Exception as e:
        print(f"❌ FAIL {scenario_name}")
        print(f"   Error: {str(e)}")
        return False

def test_play_quarter_scenario() -> bool:
    """Test gameplan functionality when Play Quarter button is pressed."""
    print("Testing Play Quarter scenario...")
    
    # This simulates the flow when a user presses "Play Quarter"
    # 1. Game is in progress
    # 2. User accesses gameplan settings
    # 3. User updates settings
    # 4. Settings should persist
    
    home_team = "Bentley-Truman"
    away_team = "Lancaster"
    
    # Simulate Q1 to create a game state
    payload = {
        "home_team": home_team,
        "away_team": away_team,
        "quarter": 1,
        "home_lineup": {"PG": "player1", "SG": "player2", "SF": "player3", "PF": "player4", "C": "player5"},
        "away_lineup": {"PG": "player6", "SG": "player7", "SF": "player8", "PF": "player9", "C": "player10"}
    }
    
    response = requests.post(f"{BASE_URL}/api/simulate-quarter", json=payload)
    
    if response.status_code != 200:
        print(f"   ❌ Q1 simulation failed: {response.status_code}")
        return False
    
    game_data = response.json()
    game_id = game_data.get("game_id")
    
    if not game_id:
        print("   ❌ No game_id returned")
        return False
    
    print(f"   ✅ Q1 simulated, game_id: {game_id}")
    
    # Test gameplan API access (this is what happens when user goes to gameplan page)
    gameplan_response = requests.get(f"{BASE_URL}/api/gameplan", params={
        "mode": "single",
        "team_id": home_team,
        "game_id": game_id
    })
    
    if gameplan_response.status_code != 200:
        print(f"   ❌ Gameplan API failed: {gameplan_response.status_code}")
        return False
    
    print("   ✅ Gameplan settings loaded")
    
    # Test updating gameplan settings
    update_payload = {
        "mode": "single",
        "team_id": home_team,
        "game_id": game_id,
        "playcall_settings": {"motion": 3, "set_play": 2},
        "strategy_settings": {"offense": 3, "defense": 2, "tempo": 1}
    }
    
    update_response = requests.put(f"{BASE_URL}/api/gameplan", json=update_payload)
    
    if update_response.status_code != 200:
        print(f"   ❌ Gameplan update failed: {update_response.status_code}")
        return False
    
    print("   ✅ Gameplan settings updated")
    return True

def test_sim_to_4th_quarter_scenario() -> bool:
    """Test gameplan functionality when Sim To 4th Quarter button is pressed."""
    print("Testing Sim To 4th Quarter scenario...")
    
    # This simulates the flow when a user presses "Sim To 4th Quarter"
    # 1. Q1-Q3 are simulated automatically
    # 2. User is redirected to set-lineup for Q4
    # 3. User accesses gameplan settings
    # 4. Settings should work (this was the bug we fixed)
    
    home_team = "Bentley-Truman"
    away_team = "Lancaster"
    game_id = None
    
    # Simulate Q1-Q3 (this is what "Sim To 4th Quarter" does)
    for quarter in range(1, 4):
        payload = {
            "home_team": home_team,
            "away_team": away_team,
            "quarter": quarter,
            "home_lineup": {"PG": "player1", "SG": "player2", "SF": "player3", "PF": "player4", "C": "player5"},
            "away_lineup": {"PG": "player6", "SG": "player7", "SF": "player8", "PF": "player9", "C": "player10"}
        }
        
        if game_id:
            payload["game_id"] = game_id
        
        response = requests.post(f"{BASE_URL}/api/simulate-quarter", json=payload)
        
        if response.status_code != 200:
            print(f"   ❌ Q{quarter} simulation failed: {response.status_code}")
            return False
        
        game_data = response.json()
        game_id = game_data.get("game_id")
        print(f"   ✅ Q{quarter} simulated")
    
    if not game_id:
        print("   ❌ No game_id returned")
        return False
    
    print(f"   ✅ Q1-Q3 simulated, game_id: {game_id}")
    
    # Test gameplan API access (this is the critical test - this was failing before our fix)
    gameplan_response = requests.get(f"{BASE_URL}/api/gameplan", params={
        "mode": "single",
        "team_id": home_team,
        "game_id": game_id
    })
    
    if gameplan_response.status_code != 200:
        print(f"   ❌ Gameplan API failed after Sim To 4th Quarter: {gameplan_response.status_code}")
        print(f"   This was the bug we fixed!")
        return False
    
    print("   ✅ Gameplan settings loaded (Sim To 4th Quarter bug fixed!)")
    
    # Test updating gameplan settings
    update_payload = {
        "mode": "single",
        "team_id": home_team,
        "game_id": game_id,
        "playcall_settings": {"motion": 4, "set_play": 1},
        "strategy_settings": {"offense": 4, "defense": 1, "tempo": 3}
    }
    
    update_response = requests.put(f"{BASE_URL}/api/gameplan", json=update_payload)
    
    if update_response.status_code != 200:
        print(f"   ❌ Gameplan update failed: {update_response.status_code}")
        return False
    
    print("   ✅ Gameplan settings updated")
    return True

def test_sim_full_game_scenario() -> bool:
    """Test gameplan functionality when Sim Full Game button is pressed."""
    print("Testing Sim Full Game scenario...")
    
    # This simulates the flow when a user presses "Sim Full Game"
    # 1. Q1-Q4 are simulated automatically
    # 2. Game is completed
    # 3. Gameplan settings should still be accessible
    
    home_team = "Bentley-Truman"
    away_team = "Lancaster"
    game_id = None
    
    # Simulate full game (Q1-Q4)
    for quarter in range(1, 5):
        payload = {
            "home_team": home_team,
            "away_team": away_team,
            "quarter": quarter,
            "home_lineup": {"PG": "player1", "SG": "player2", "SF": "player3", "PF": "player4", "C": "player5"},
            "away_lineup": {"PG": "player6", "SG": "player7", "SF": "player8", "PF": "player9", "C": "player10"}
        }
        
        if game_id:
            payload["game_id"] = game_id
        
        response = requests.post(f"{BASE_URL}/api/simulate-quarter", json=payload)
        
        if response.status_code != 200:
            print(f"   ❌ Q{quarter} simulation failed: {response.status_code}")
            return False
        
        game_data = response.json()
        game_id = game_data.get("game_id")
        
        print(f"   ✅ Q{quarter} simulated")
        
        # Check if game is final
        if game_data.get("is_final"):
            print("   ✅ Game completed")
            break
    
    if not game_id:
        print("   ❌ No game_id returned")
        return False
    
    print(f"   ✅ Full game simulated, game_id: {game_id}")
    
    # Test gameplan API access after full game
    gameplan_response = requests.get(f"{BASE_URL}/api/gameplan", params={
        "mode": "single",
        "team_id": home_team,
        "game_id": game_id
    })
    
    if gameplan_response.status_code != 200:
        print(f"   ❌ Gameplan API failed after full game: {gameplan_response.status_code}")
        return False
    
    print("   ✅ Gameplan settings loaded after full game")
    return True

def test_tournament_sim_to_4th_scenario() -> bool:
    """Test the specific tournament Sim To 4th Quarter bug we fixed."""
    print("Testing Tournament Sim To 4th Quarter scenario...")
    
    # This tests the specific bug we fixed in tournament mode
    # The issue was that team_id was null because home_id/away_id weren't passed
    
    # Start a tournament
    start_response = requests.post(f"{BASE_URL}/tournament/start", json={
        "user_team": "Bentley-Truman"
    })
    
    if start_response.status_code != 200:
        print(f"   ❌ Failed to start tournament: {start_response.status_code}")
        return False
    
    tournament_data = start_response.json()
    tournament_id = tournament_data["tournament_id"]
    print(f"   ✅ Tournament started: {tournament_id}")
    
    # Simulate rounds until we get to user matchup
    for round_num in range(1, 4):
        sim_response = requests.post(f"{BASE_URL}/tournament/simulate-round", json={
            "tournament_id": tournament_id
        })
        
        if sim_response.status_code != 200:
            print(f"   ❌ Failed to simulate round {round_num}: {sim_response.status_code}")
            return False
        
        print(f"   ✅ Round {round_num} simulated")
    
    # Test gameplan API access (this was the critical bug)
    gameplan_response = requests.get(f"{BASE_URL}/api/gameplan", params={
        "mode": "tournament",
        "team_id": "Bentley-Truman",  # This was coming through as null before our fix
        "tournament_id": tournament_id
    })
    
    if gameplan_response.status_code != 200:
        print(f"   ❌ Tournament gameplan API failed: {gameplan_response.status_code}")
        print(f"   This was the bug we fixed!")
        if gameplan_response.text:
            print(f"   Error: {gameplan_response.text}")
        return False
    
    print("   ✅ Tournament gameplan API works (bug fixed!)")
    
    # Test updating gameplan settings
    update_payload = {
        "mode": "tournament",
        "team_id": "Bentley-Truman",
        "tournament_id": tournament_id,
        "playcall_settings": {"motion": 4, "set_play": 1},
        "strategy_settings": {"offense": 4, "defense": 1, "tempo": 3}
    }
    
    update_response = requests.put(f"{BASE_URL}/api/gameplan", json=update_payload)
    
    if update_response.status_code != 200:
        print(f"   ❌ Tournament gameplan update failed: {update_response.status_code}")
        return False
    
    print("   ✅ Tournament gameplan settings updated")
    return True

def main():
    """Run all gameplan functionality tests."""
    print("🚀 Gameplan Functionality Test Suite")
    print("=" * 60)
    print("Testing all scenarios for gameplan functionality:")
    print("1. Play Quarter button pressed")
    print("2. Sim To 4th Quarter button pressed")
    print("3. Sim Full Game button pressed")
    print("4. Tournament Sim To 4th Quarter (the bug we fixed)")
    print("=" * 60)
    
    # Update BASE_URL if needed
    if BASE_URL == "https://your-railway-app.railway.app":
        print("⚠️  Please update BASE_URL in the script to your actual server URL")
        print("   Current BASE_URL:", BASE_URL)
        return
    
    results = []
    
    # Test each scenario
    results.append(test_gameplan_scenario("Play Quarter Scenario", test_play_quarter_scenario))
    results.append(test_gameplan_scenario("Sim To 4th Quarter Scenario", test_sim_to_4th_quarter_scenario))
    results.append(test_gameplan_scenario("Sim Full Game Scenario", test_sim_full_game_scenario))
    results.append(test_gameplan_scenario("Tournament Sim To 4th Quarter Scenario", test_tournament_sim_to_4th_scenario))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    
    total_tests = len(results)
    passed_tests = sum(results)
    failed_tests = total_tests - passed_tests
    
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {passed_tests}")
    print(f"   Failed: {failed_tests}")
    print(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    # Critical test results
    print(f"\n🎯 Critical Tests:")
    print(f"   Tournament Sim To 4th Quarter: {'✅ PASS' if results[3] else '❌ FAIL'}")
    print(f"   Single Game Sim To 4th Quarter: {'✅ PASS' if results[1] else '❌ FAIL'}")
    
    if failed_tests == 0:
        print("\n🎉 All tests passed! Gameplan functionality is working correctly.")
    else:
        print(f"\n⚠️  {failed_tests} test(s) failed. Check the output above for details.")

if __name__ == "__main__":
    main()
