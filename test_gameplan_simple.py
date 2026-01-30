#!/usr/bin/env python3
"""
Simple test runner for gameplan functionality.

Usage:
    python test_gameplan_simple.py

This script tests the specific scenarios you mentioned:
1. Play Quarter button pressed
2. Sim To 4th Quarter button pressed  
3. Sim Full Game button pressed

It focuses on the core functionality without requiring complex setup.
"""

import requests
import json
import uuid

def test_basic_gameplan_api():
    """Test basic gameplan API functionality."""
    print("🧪 Testing Basic Gameplan API...")
    
    # Test with a simple request
    try:
        response = requests.get("http://localhost:8000/api/gameplan", params={
            "mode": "single",
            "team_id": "Bentley-Truman",
            "game_id": str(uuid.uuid4())
        })
        
        if response.status_code == 200:
            print("   ✅ Basic gameplan API works")
            return True
        else:
            print(f"   ❌ Basic gameplan API failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Cannot connect to server. Make sure the server is running on localhost:8000")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_sim_to_4th_quarter_flow():
    """Test the Sim To 4th Quarter flow specifically."""
    print("\n🧪 Testing Sim To 4th Quarter Flow...")
    
    try:
        home_team = "Bentley-Truman"
        away_team = "Lancaster"
        game_id = None
        
        # Simulate Q1-Q3 (what Sim To 4th Quarter does)
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
            
            response = requests.post("http://localhost:8000/api/simulate-quarter", json=payload)
            
            if response.status_code != 200:
                print(f"   ❌ Q{quarter} simulation failed: {response.status_code}")
                return False
            
            game_data = response.json()
            game_id = game_data.get("game_id")
            print(f"   ✅ Q{quarter} simulated")
        
        if not game_id:
            print("   ❌ No game_id returned")
            return False
        
        # Test gameplan API access (this was the bug)
        gameplan_response = requests.get("http://localhost:8000/api/gameplan", params={
            "mode": "single",
            "team_id": home_team,
            "game_id": game_id
        })
        
        if gameplan_response.status_code != 200:
            print(f"   ❌ Gameplan API failed after Sim To 4th Quarter: {gameplan_response.status_code}")
            return False
        
        print("   ✅ Gameplan API works after Sim To 4th Quarter")
        return True
        
    except requests.exceptions.ConnectionError:
        print("   ❌ Cannot connect to server. Make sure the server is running on localhost:8000")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_tournament_gameplan():
    """Test tournament gameplan functionality."""
    print("\n🧪 Testing Tournament Gameplan...")
    
    try:
        # Start a tournament
        start_response = requests.post("http://localhost:8000/tournament/start", json={
            "user_team_id": "Bentley-Truman"
        })
        
        if start_response.status_code != 200:
            print(f"   ❌ Failed to start tournament: {start_response.status_code}")
            return False
        
        tournament_data = start_response.json()
        tournament_id = tournament_data["_id"]
        print(f"   ✅ Tournament started: {tournament_id}")
        
        # Test gameplan API access (this was the critical bug)
        gameplan_response = requests.get("http://localhost:8000/api/gameplan", params={
            "mode": "tournament",
            "team_id": "Bentley-Truman",
            "tournament_id": tournament_id
        })
        
        if gameplan_response.status_code != 200:
            print(f"   ❌ Tournament gameplan API failed: {gameplan_response.status_code}")
            return False
        
        print("   ✅ Tournament gameplan API works")
        return True
        
    except requests.exceptions.ConnectionError:
        print("   ❌ Cannot connect to server. Make sure the server is running on localhost:8000")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Run the tests."""
    print("🚀 Gameplan Functionality Tests")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        print("✅ Server is running")
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running. Please start the server first.")
        print("   Run: python BackEnd/run.py")
        return
    except Exception as e:
        print(f"❌ Error connecting to server: {e}")
        return
    
    print("\nRunning tests...")
    
    # Run tests
    results = []
    results.append(test_basic_gameplan_api())
    results.append(test_sim_to_4th_quarter_flow())
    results.append(test_tournament_gameplan())
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    
    total_tests = len(results)
    passed_tests = sum(results)
    failed_tests = total_tests - passed_tests
    
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {passed_tests}")
    print(f"   Failed: {failed_tests}")
    
    if failed_tests == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {failed_tests} test(s) failed.")

if __name__ == "__main__":
    main()
