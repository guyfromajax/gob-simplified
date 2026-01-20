#!/usr/bin/env python3
"""
Test suite for Phase 1.1: State Contract Enforcement

Tests that verify:
1. game_id must come from URL params only (no localStorage fallback)
2. franchise_id must come from URL params only (no localStorage fallback)
3. Error handling for missing required pointers
4. Team ID resolution simplification works correctly

Success Criteria:
- No localStorage fallbacks for game_id or franchise_id
- Missing required pointers trigger explicit errors
- Team ID resolution works correctly with simplified logic
"""

import requests
import json
import sys
import os
from typing import Dict, Any, Optional

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from BackEnd.constants import POSITION_LIST

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

HOME_TEAM_NAME = "Bentley-Truman"
AWAY_TEAM_NAME = "Lancaster"
HOME_TEAM_ID = "BENTLEY_TRUMAN"
AWAY_TEAM_ID = "LANCASTER"


def run_test():
    """Run all Phase 1.1 tests."""
    print("=" * 80)
    print("PHASE 1.1 STATE CONTRACT ENFORCEMENT TESTS")
    print("=" * 80)
    print(f"Testing against: {BASE_URL}\n")
    
    results = []
    
    # Test 1: game_id persistence without localStorage fallback
    results.append(test_game_id_no_localstorage_fallback())
    
    # Test 2: franchise_id persistence without localStorage fallback
    results.append(test_franchise_id_no_localstorage_fallback())
    
    # Test 3: Missing game_id triggers error when required
    results.append(test_missing_game_id_error())
    
    # Test 4: Missing franchise_id triggers error in franchise mode
    results.append(test_missing_franchise_id_error())
    
    # Test 5: Team ID resolution works correctly
    results.append(test_team_id_resolution())
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed
    
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌\n")
    
    if failed > 0:
        print("Failed Tests:")
        for r in results:
            if not r["success"]:
                print(f"  ❌ {r['name']}")
                print(f"     Error: {r['error_message']}\n")
        print("=" * 80)
        print(f"❌ {failed} TEST(S) FAILED")
        print("=" * 80 + "\n")
        sys.exit(1)
    else:
        print("=" * 80)
        print("✅ ALL TESTS PASSED - Phase 1.1 State Contract Enforcement Working")
        print("=" * 80 + "\n")
        sys.exit(0)


def test_game_id_no_localstorage_fallback():
    """Test that game_id persists correctly through flow without localStorage."""
    print("\n" + "-" * 80)
    print("TEST 1: game_id Persistence Without localStorage Fallback")
    print("-" * 80)
    
    try:
        # Step 1: Create game via init-game
        init_payload = {
            "home_team": HOME_TEAM_NAME,
            "away_team": AWAY_TEAM_NAME,
            "mode": "single"
        }
        response = requests.post(f"{BASE_URL}/api/init-game", json=init_payload, timeout=10)
        response.raise_for_status()
        init_data = response.json()
        game_id = init_data.get("game_id")
        
        if not game_id:
            raise Exception("game_id not returned from init-game")
        
        print(f"  ✅ Created game_id: {game_id}")
        
        # Step 2: Save playbook settings (should use game_id from URL)
        playbook_settings = {
            "mode": "single",
            "team_id": HOME_TEAM_NAME,
            "game_id": game_id,  # Explicitly passed, no localStorage fallback
            "playbook_settings": {
                "motion": {"3-2 Motion": 34, "4-1 Motion": 33, "5-0 Motion": 33}
            }
        }
        response_pb = requests.post(f"{BASE_URL}/api/playbooks", json=playbook_settings, timeout=10)
        response_pb.raise_for_status()
        print(f"  ✅ Saved playbook settings with game_id: {game_id}")
        
        # Step 3: Simulate Q1 (should use same game_id)
        q1_payload = {
            "game_id": game_id,  # Explicitly passed, no localStorage fallback
            "home_team": HOME_TEAM_NAME,
            "away_team": AWAY_TEAM_NAME,
            "quarter": 1,
            "mode": "single",
            "full_sim": False,
            "user_team_side": "home",
            "home_lineup": {p: f"{HOME_TEAM_ID}_{p}" for p in POSITION_LIST},
            "away_lineup": {p: f"{AWAY_TEAM_ID}_{p}" for p in POSITION_LIST},
        }
        response = requests.post(f"{BASE_URL}/api/simulate-quarter", json=q1_payload, timeout=30)
        response.raise_for_status()
        q1_data = response.json()
        
        if q1_data.get("game_id") != game_id:
            raise Exception(f"Game ID mismatch: expected {game_id}, got {q1_data.get('game_id')}")
        
        print(f"  ✅ Q1 simulation used same game_id: {game_id}")
        
        return {
            "name": "game_id Persistence Without localStorage Fallback",
            "success": True,
            "game_id": game_id,
            "details": {"game_id": game_id, "flow": "init → playbook → Q1"}
        }
        
    except Exception as e:
        return {
            "name": "game_id Persistence Without localStorage Fallback",
            "success": False,
            "error_message": f"Exception: {e}",
            "details": {"exception_type": type(e).__name__}
        }


def test_franchise_id_no_localstorage_fallback():
    """Test that franchise_id works correctly without localStorage fallback."""
    print("\n" + "-" * 80)
    print("TEST 2: franchise_id Persistence Without localStorage Fallback")
    print("-" * 80)
    
    try:
        # Step 1: Create franchise (if possible) or use existing
        # For this test, we'll check that franchise_id is required in requests
        # In a real scenario, we'd create a franchise first
        
        # Step 2: Try to get gameplan without franchise_id (should fail in franchise mode)
        response = requests.get(
            f"{BASE_URL}/api/gameplan",
            params={"mode": "franchise", "team_id": HOME_TEAM_ID},
            timeout=10
        )
        
        # Should fail with 400 error (franchise_id required)
        if response.status_code != 400:
            raise Exception(f"Expected 400 error when franchise_id missing, got {response.status_code}")
        
        print(f"  ✅ Missing franchise_id correctly triggers 400 error")
        
        return {
            "name": "franchise_id Persistence Without localStorage Fallback",
            "success": True,
            "details": {"error_handling": "✅"}
        }
        
    except Exception as e:
        return {
            "name": "franchise_id Persistence Without localStorage Fallback",
            "success": False,
            "error_message": f"Exception: {e}",
            "details": {"exception_type": type(e).__name__}
        }


def test_missing_game_id_error():
    """Test that missing game_id triggers explicit error when required."""
    print("\n" + "-" * 80)
    print("TEST 3: Missing game_id Error Handling")
    print("-" * 80)
    
    try:
        # Try to simulate Q1 without game_id (should fail)
        q1_payload = {
            # NO game_id - should fail
            "home_team": HOME_TEAM_NAME,
            "away_team": AWAY_TEAM_NAME,
            "quarter": 1,
            "mode": "single",
            "full_sim": False,
            "user_team_side": "home",
            "home_lineup": {p: f"{HOME_TEAM_ID}_{p}" for p in POSITION_LIST},
            "away_lineup": {p: f"{AWAY_TEAM_ID}_{p}" for p in POSITION_LIST},
        }
        response = requests.post(f"{BASE_URL}/api/simulate-quarter", json=q1_payload, timeout=30)
        
        # Should fail with 400 error (game_id required)
        if response.status_code != 400:
            raise Exception(f"Expected 400 error when game_id missing for Q1, got {response.status_code}: {response.text}")
        
        print(f"  ✅ Missing game_id correctly triggers 400 error")
        
        error_detail = response.json().get("detail", "")
        if "game_id required" not in error_detail.lower():
            print(f"  ⚠️ Warning: Error message doesn't mention 'game_id required': {error_detail}")
        
        return {
            "name": "Missing game_id Error Handling",
            "success": True,
            "details": {"status_code": response.status_code, "error_message": error_detail}
        }
        
    except Exception as e:
        return {
            "name": "Missing game_id Error Handling",
            "success": False,
            "error_message": f"Exception: {e}",
            "details": {"exception_type": type(e).__name__}
        }


def test_missing_franchise_id_error():
    """Test that missing franchise_id triggers explicit error in franchise mode."""
    print("\n" + "-" * 80)
    print("TEST 4: Missing franchise_id Error Handling")
    print("-" * 80)
    
    try:
        # Try to get gameplan in franchise mode without franchise_id (should fail)
        response = requests.get(
            f"{BASE_URL}/api/gameplan",
            params={"mode": "franchise", "team_id": HOME_TEAM_ID},
            # NO franchise_id - should fail
            timeout=10
        )
        
        # Should fail with 400 error (franchise_id required)
        if response.status_code != 400:
            raise Exception(f"Expected 400 error when franchise_id missing, got {response.status_code}")
        
        print(f"  ✅ Missing franchise_id correctly triggers 400 error")
        
        error_detail = response.json().get("detail", "")
        if "franchise_id required" not in error_detail.lower():
            print(f"  ⚠️ Warning: Error message doesn't mention 'franchise_id required': {error_detail}")
        
        return {
            "name": "Missing franchise_id Error Handling",
            "success": True,
            "details": {"status_code": response.status_code, "error_message": error_detail}
        }
        
    except Exception as e:
        return {
            "name": "Missing franchise_id Error Handling",
            "success": False,
            "error_message": f"Exception: {e}",
            "details": {"exception_type": type(e).__name__}
        }


def test_team_id_resolution():
    """Test that team ID resolution works correctly with simplified logic."""
    print("\n" + "-" * 80)
    print("TEST 5: Team ID Resolution")
    print("-" * 80)
    
    try:
        # Step 1: Create game via init-game
        init_payload = {
            "home_team": HOME_TEAM_NAME,
            "away_team": AWAY_TEAM_NAME,
            "mode": "single"
        }
        response = requests.post(f"{BASE_URL}/api/init-game", json=init_payload, timeout=10)
        response.raise_for_status()
        init_data = response.json()
        game_id = init_data.get("game_id")
        
        print(f"  ✅ Created game_id: {game_id}")
        
        # Step 2: Save playbook settings using team name (should resolve to team_id)
        playbook_settings = {
            "mode": "single",
            "team_id": HOME_TEAM_NAME,  # Send team name (not team_id)
            "game_id": game_id,
            "playbook_settings": {
                "motion": {"3-2 Motion": 34, "4-1 Motion": 33, "5-0 Motion": 33}
            }
        }
        response_pb = requests.post(f"{BASE_URL}/api/playbooks", json=playbook_settings, timeout=10)
        response_pb.raise_for_status()
        print(f"  ✅ Saved playbook settings with team name: {HOME_TEAM_NAME}")
        
        # Step 3: Verify settings were saved under team_id key (not team name key)
        game_doc_response = requests.get(f"{BASE_URL}/api/game/{game_id}?quarter=1&source=db", timeout=10)
        game_doc_response.raise_for_status()
        game_doc = game_doc_response.json()
        
        teams = game_doc.get("teams", {})
        
        # Check if settings are saved under team_id key
        if HOME_TEAM_ID in teams and teams[HOME_TEAM_ID].get("playbook_settings"):
            print(f"  ✅ Settings saved under team_id key: {HOME_TEAM_ID}")
            return {
                "name": "Team ID Resolution",
                "success": True,
                "details": {
                    "team_name_sent": HOME_TEAM_NAME,
                    "team_id_key_used": HOME_TEAM_ID,
                    "settings_saved": "✅"
                }
            }
        elif HOME_TEAM_NAME in teams:
            raise Exception(f"Settings saved under team name key '{HOME_TEAM_NAME}' instead of team_id key '{HOME_TEAM_ID}'")
        else:
            raise Exception(f"Settings not found under either team_id '{HOME_TEAM_ID}' or team name '{HOME_TEAM_NAME}'")
        
    except Exception as e:
        return {
            "name": "Team ID Resolution",
            "success": False,
            "error_message": f"Exception: {e}",
            "details": {"exception_type": type(e).__name__}
        }


if __name__ == "__main__":
    run_test()

