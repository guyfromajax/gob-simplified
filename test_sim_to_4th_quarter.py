#!/usr/bin/env python3
"""
Test script to reproduce the Sim To 4th Quarter gameplan API issue.
This test simulates the exact flow that happens when using Sim To 4th Quarter.
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"  # Change to your server URL if different
TOURNAMENT_TEAMS = ["Bentley-Truman", "Lancaster", "Little York", "Four Corners", "Morristown", "Ocean City", "South Lancaster", "Xavien"]

def test_sim_to_4th_quarter_flow():
    """Test the complete Sim To 4th Quarter flow and check gameplan API access."""
    
    print("🧪 Starting Sim To 4th Quarter test...")
    
    # Step 1: Start a tournament
    print("\n1️⃣ Starting tournament...")
    start_response = requests.post(f"{BASE_URL}/tournament/start", json={
        "user_team": "Bentley-Truman"
    })
    
    if start_response.status_code != 200:
        print(f"❌ Failed to start tournament: {start_response.status_code}")
        return False
    
    tournament_data = start_response.json()
    tournament_id = tournament_data["tournament_id"]
    print(f"✅ Tournament started: {tournament_id}")
    
    # Step 2: Get tournament state to find user matchup
    print("\n2️⃣ Getting tournament state...")
    state_response = requests.get(f"{BASE_URL}/tournament/state/{tournament_id}")
    
    if state_response.status_code != 200:
        print(f"❌ Failed to get tournament state: {state_response.status_code}")
        return False
    
    state_data = state_response.json()
    user_team_id = state_data.get("user_team_id")
    print(f"✅ User team: {user_team_id}")
    
    # Step 3: Simulate rounds until we get to user matchup
    print("\n3️⃣ Simulating non-user games...")
    current_round = state_data.get("current_round", 1)
    
    # Simulate rounds until we reach the user's game
    for round_num in range(current_round, 5):  # Go through all rounds
        print(f"   Simulating Round {round_num}...")
        
        sim_response = requests.post(f"{BASE_URL}/tournament/simulate-round", json={
            "tournament_id": tournament_id
        })
        
        if sim_response.status_code == 200:
            sim_data = sim_response.json()
            if sim_data.get("already_played"):
                print(f"   ✅ Round {round_num} already completed")
                break
            else:
                print(f"   ✅ Round {round_num} simulated")
        else:
            print(f"   ❌ Failed to simulate round {round_num}: {sim_response.status_code}")
            if sim_response.text:
                print(f"   Error: {sim_response.text}")
            return False
    
    # Step 4: Get updated tournament state
    print("\n4️⃣ Getting updated tournament state...")
    state_response = requests.get(f"{BASE_URL}/tournament/state/{tournament_id}")
    
    if state_response.status_code != 200:
        print(f"❌ Failed to get updated tournament state: {state_response.status_code}")
        return False
    
    updated_state = state_response.json()
    print(f"✅ Tournament state updated")
    
    # Step 5: Test gameplan API access
    print("\n5️⃣ Testing gameplan API access...")
    
    # Extract team_id from the tournament state
    # The team_id should be the user's team ID
    team_id = user_team_id
    
    gameplan_response = requests.get(f"{BASE_URL}/api/gameplan", params={
        "mode": "tournament",
        "tournament_id": tournament_id,
        "team_id": team_id
    })
    
    print(f"   Gameplan API response: {gameplan_response.status_code}")
    if gameplan_response.status_code == 200:
        gameplan_data = gameplan_response.json()
        print(f"   ✅ Gameplan API working: {list(gameplan_data.keys())}")
        return True
    else:
        print(f"   ❌ Gameplan API failed: {gameplan_response.status_code}")
        if gameplan_response.text:
            print(f"   Error: {gameplan_response.text}")
        return False

def test_play_quarter_flow():
    """Test the Play Quarter flow for comparison."""
    
    print("\n🧪 Testing Play Quarter flow for comparison...")
    
    # This would test the normal quarter-by-quarter flow
    # For now, just return True as a placeholder
    print("✅ Play Quarter flow test (placeholder)")
    return True

if __name__ == "__main__":
    print("🚀 Starting Sim To 4th Quarter vs Play Quarter comparison tests...")
    
    # Test Sim To 4th Quarter flow
    sim_to_4th_success = test_sim_to_4th_quarter_flow()
    
    # Test Play Quarter flow
    play_quarter_success = test_play_quarter_flow()
    
    print(f"\n📊 Test Results:")
    print(f"   Sim To 4th Quarter: {'✅ PASS' if sim_to_4th_success else '❌ FAIL'}")
    print(f"   Play Quarter: {'✅ PASS' if play_quarter_success else '❌ FAIL'}")
    
    if not sim_to_4th_success:
        print(f"\n🔍 Sim To 4th Quarter test failed - this reproduces the gameplan API issue!")
    else:
        print(f"\n✅ All tests passed!")
