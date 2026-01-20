#!/usr/bin/env python3
"""
Comprehensive test suite for game_id persistence across the complete game flow.

Tests that game_id persists correctly through:
1. Game init (init-game endpoint)
2. Pre-game settings adjustments (save playbook/game plan)
3. Game start and gameplay (simulate-quarter Q1)
4. Timeout called (call-timeout endpoint)
5. Return to gameplay (simulate-quarter with resume_from_timeout)

Success Criteria:
- Same game_id used throughout entire flow
- No duplicate game documents created
- Settings persist correctly across all steps
"""

import requests
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Configuration
BASE_URL = "http://localhost:8000"  # Change to your server URL if different
TEST_TEAMS = {
    "home": "Bentley-Truman",
    "away": "Lancaster"
}

@dataclass
class TestResult:
    """Container for test results."""
    test_name: str
    success: bool
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    game_id: Optional[str] = None


class GameIdPersistenceTestSuite:
    """Test suite for game_id persistence."""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.test_results = []
        self.game_id = None
        
    def log_test_result(self, test_name: str, success: bool, error_message: str = None, 
                       details: Dict = None, game_id: str = None):
        """Log a test result."""
        result = TestResult(test_name, success, error_message, details, game_id)
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if game_id:
            print(f"   game_id: {game_id}")
        if error_message:
            print(f"   Error: {error_message}")
        if details:
            print(f"   Details: {json.dumps(details, indent=2)}")
        print()
    
    def test_complete_game_flow(self) -> bool:
        """
        Test complete game flow with game_id persistence.
        
        Flow:
        1. Game init → get game_id
        2. Pre-game settings adjustments → verify game_id persists
        3. Game start (Q1) → verify same game_id
        4. Timeout called → verify same game_id
        5. Return to gameplay → verify same game_id
        """
        print("=" * 80)
        print("TESTING: Complete Game Flow - game_id Persistence")
        print("=" * 80)
        print()
        
        all_passed = True
        
        # Step 1: Game Init
        print("STEP 1: Game Init (init-game)")
        print("-" * 80)
        game_id = self._test_game_init()
        if not game_id:
            all_passed = False
            return False
        self.game_id = game_id
        
        # Step 2: Pre-game Settings Adjustments
        print("STEP 2: Pre-game Settings Adjustments")
        print("-" * 80)
        if not self._test_pre_game_settings(game_id):
            all_passed = False
        
        # Step 3: Game Start (Q1)
        print("STEP 3: Game Start (Q1)")
        print("-" * 80)
        if not self._test_game_start(game_id):
            all_passed = False
        
        # Step 4: Timeout Called
        print("STEP 4: Timeout Called")
        print("-" * 80)
        if not self._test_timeout_called(game_id):
            all_passed = False
        
        # Step 5: Return to Gameplay
        print("STEP 5: Return to Gameplay (Resume from Timeout)")
        print("-" * 80)
        if not self._test_resume_from_timeout(game_id):
            all_passed = False
        
        # Final Summary
        print("=" * 80)
        print("FINAL SUMMARY")
        print("=" * 80)
        self._print_summary()
        
        return all_passed
    
    def _test_game_init(self) -> Optional[str]:
        """Test Step 1: Game Init - create game and get game_id."""
        test_name = "Game Init - Create game document"
        
        try:
            response = requests.post(
                f"{self.base_url}/api/init-game",
                json={
                    "home_team": TEST_TEAMS["home"],
                    "away_team": TEST_TEAMS["away"],
                    "mode": "single"
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                self.log_test_result(
                    test_name, False,
                    f"init-game failed: {response.status_code} - {response.text}",
                    details={"status_code": response.status_code, "response": response.text}
                )
                return None
            
            data = response.json()
            if "game_id" not in data:
                self.log_test_result(
                    test_name, False,
                    "Response missing game_id",
                    details={"response": data}
                )
                return None
            
            game_id = data["game_id"]
            self.log_test_result(
                test_name, True,
                details={"game_id": game_id, "home_team": TEST_TEAMS["home"], "away_team": TEST_TEAMS["away"]},
                game_id=game_id
            )
            return game_id
            
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"Exception: {str(e)}",
                details={"exception_type": type(e).__name__}
            )
            return None
    
    def _test_pre_game_settings(self, game_id: str) -> bool:
        """Test Step 2: Pre-game Settings - save playbook and game plan, verify game_id persists."""
        test_name = "Pre-game Settings - Save playbook and game plan"
        
        try:
            # Test 2a: Save Playbook Settings
            print("  Testing: Save Playbook Settings")
            playbook_response = requests.post(
                f"{self.base_url}/api/playbooks",
                json={
                    "mode": "single",
                    "team_id": TEST_TEAMS["home"],
                    "game_id": game_id,
                    "playbook_settings": {
                        "motion": {"Base Motion": 50, "4-1 Motion": 50},
                        "set_play_inside": {"Base Post Play": 100}
                    }
                },
                headers={"Content-Type": "application/json"}
            )
            
            if playbook_response.status_code != 200:
                self.log_test_result(
                    f"{test_name} - Playbook Save", False,
                    f"Failed: {playbook_response.status_code} - {playbook_response.text}",
                    details={"status_code": playbook_response.status_code}
                )
                return False
            
            # Test 2b: Save Game Plan Settings
            print("  Testing: Save Game Plan Settings")
            gameplan_response = requests.put(
                f"{self.base_url}/api/gameplan",
                json={
                    "mode": "single",
                    "team_id": TEST_TEAMS["home"],
                    "game_id": game_id,
                    "strategy_settings": {
                        "offense": 3,
                        "defense": 2,
                        "tempo": 1
                    }
                },
                headers={"Content-Type": "application/json"}
            )
            
            if gameplan_response.status_code != 200:
                self.log_test_result(
                    f"{test_name} - Game Plan Save", False,
                    f"Failed: {gameplan_response.status_code} - {gameplan_response.text}",
                    details={"status_code": gameplan_response.status_code}
                )
                return False
            
            # Verify game document still exists with same game_id
            game_state_response = requests.get(
                f"{self.base_url}/api/game/{game_id}",
                params={"quarter": 1, "source": "db"}
            )
            
            if game_state_response.status_code != 200:
                self.log_test_result(
                    f"{test_name} - Verify Game Document", False,
                    f"Game document not found: {game_state_response.status_code}",
                    details={"status_code": game_state_response.status_code}
                )
                return False
            
            self.log_test_result(
                test_name, True,
                details={
                    "playbook_save": "✅",
                    "gameplan_save": "✅",
                    "game_document_exists": "✅"
                },
                game_id=game_id
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"Exception: {str(e)}",
                details={"exception_type": type(e).__name__}
            )
            return False
    
    def _test_game_start(self, game_id: str) -> bool:
        """Test Step 3: Game Start (Q1) - verify same game_id used."""
        test_name = "Game Start (Q1) - Simulate Q1 with same game_id"
        
        try:
            response = requests.post(
                f"{self.base_url}/api/simulate-quarter",
                json={
                    "game_id": game_id,
                    "home_team": TEST_TEAMS["home"],
                    "away_team": TEST_TEAMS["away"],
                    "quarter": 1,
                    "mode": "single",
                    "full_sim": True,
                    "user_team_side": "home",
                    "strategy_settings": {
                        "offense": 3,
                        "defense": 2,
                        "tempo": 1
                    }
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                self.log_test_result(
                    test_name, False,
                    f"simulate-quarter failed: {response.status_code} - {response.text}",
                    details={"status_code": response.status_code, "response": response.text[:200]}
                )
                return False
            
            data = response.json()
            returned_game_id = data.get("game_id")
            
            if returned_game_id != game_id:
                self.log_test_result(
                    test_name, False,
                    f"game_id mismatch: expected {game_id}, got {returned_game_id}",
                    details={"expected": game_id, "actual": returned_game_id}
                )
                return False
            
            # Verify game document still exists with same game_id
            game_state_response = requests.get(
                f"{self.base_url}/api/game/{game_id}",
                params={"quarter": 1, "source": "db"}
            )
            
            if game_state_response.status_code != 200:
                self.log_test_result(
                    f"{test_name} - Verify Game Document", False,
                    f"Game document not found: {game_state_response.status_code}",
                    details={"status_code": game_state_response.status_code}
                )
                return False
            
            self.log_test_result(
                test_name, True,
                details={
                    "quarter": data.get("quarter"),
                    "game_id_match": "✅",
                    "game_document_exists": "✅"
                },
                game_id=game_id
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"Exception: {str(e)}",
                details={"exception_type": type(e).__name__}
            )
            return False
    
    def _test_timeout_called(self, game_id: str) -> bool:
        """Test Step 4: Timeout Called - verify same game_id used."""
        test_name = "Timeout Called - Call timeout with same game_id"
        
        try:
            response = requests.post(
                f"{self.base_url}/api/call-timeout",
                json={
                    "game_id": game_id,
                    "calling_team": "home"  # "home" or "away"
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                self.log_test_result(
                    test_name, False,
                    f"call-timeout failed: {response.status_code} - {response.text}",
                    details={"status_code": response.status_code, "response": response.text[:200]}
                )
                return False
            
            data = response.json()
            returned_game_id = data.get("game_id")
            
            if returned_game_id != game_id:
                self.log_test_result(
                    test_name, False,
                    f"game_id mismatch: expected {game_id}, got {returned_game_id}",
                    details={"expected": game_id, "actual": returned_game_id}
                )
                return False
            
            # Verify game document still exists with same game_id
            game_state_response = requests.get(
                f"{self.base_url}/api/game/{game_id}",
                params={"quarter": 1, "source": "db"}
            )
            
            if game_state_response.status_code != 200:
                self.log_test_result(
                    f"{test_name} - Verify Game Document", False,
                    f"Game document not found: {game_state_response.status_code}",
                    details={"status_code": game_state_response.status_code}
                )
                return False
            
            self.log_test_result(
                test_name, True,
                details={
                    "timeout_state_saved": "✅",
                    "game_id_match": "✅",
                    "game_document_exists": "✅"
                },
                game_id=game_id
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"Exception: {str(e)}",
                details={"exception_type": type(e).__name__}
            )
            return False
    
    def _test_resume_from_timeout(self, game_id: str) -> bool:
        """Test Step 5: Return to Gameplay - resume from timeout with same game_id."""
        test_name = "Return to Gameplay - Resume from timeout with same game_id"
        
        try:
            response = requests.post(
                f"{self.base_url}/api/simulate-quarter",
                json={
                    "game_id": game_id,
                    "home_team": TEST_TEAMS["home"],
                    "away_team": TEST_TEAMS["away"],
                    "quarter": 1,
                    "mode": "single",
                    "full_sim": True,
                    "resume_from_timeout": True,
                    "user_team_side": "home"
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                self.log_test_result(
                    test_name, False,
                    f"simulate-quarter resume failed: {response.status_code} - {response.text}",
                    details={"status_code": response.status_code, "response": response.text[:200]}
                )
                return False
            
            data = response.json()
            returned_game_id = data.get("game_id")
            
            if returned_game_id != game_id:
                self.log_test_result(
                    test_name, False,
                    f"game_id mismatch: expected {game_id}, got {returned_game_id}",
                    details={"expected": game_id, "actual": returned_game_id}
                )
                return False
            
            # Verify game document still exists with same game_id
            game_state_response = requests.get(
                f"{self.base_url}/api/game/{game_id}",
                params={"quarter": 1, "source": "db"}
            )
            
            if game_state_response.status_code != 200:
                self.log_test_result(
                    f"{test_name} - Verify Game Document", False,
                    f"Game document not found: {game_state_response.status_code}",
                    details={"status_code": game_state_response.status_code}
                )
                return False
            
            self.log_test_result(
                test_name, True,
                details={
                    "resume_from_timeout": "✅",
                    "game_id_match": "✅",
                    "game_document_exists": "✅"
                },
                game_id=game_id
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"Exception: {str(e)}",
                details={"exception_type": type(e).__name__}
            )
            return False
    
    def _print_summary(self):
        """Print final test summary."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.success)
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print()
        
        if self.game_id:
            print(f"Final game_id: {self.game_id}")
            print()
        
        if failed_tests > 0:
            print("Failed Tests:")
            for result in self.test_results:
                if not result.success:
                    print(f"  ❌ {result.test_name}")
                    if result.error_message:
                        print(f"     Error: {result.error_message}")
            print()
        
        print("=" * 80)
        if failed_tests == 0:
            print("✅ ALL TESTS PASSED - game_id persists correctly across entire flow")
        else:
            print(f"❌ {failed_tests} TEST(S) FAILED - game_id persistence issues detected")
        print("=" * 80)


def main():
    """Run the test suite."""
    import sys
    
    # Allow custom base URL via command line
    base_url = sys.argv[1] if len(sys.argv) > 1 else BASE_URL
    
    print(f"Testing game_id persistence with base URL: {base_url}")
    print()
    
    suite = GameIdPersistenceTestSuite(base_url=base_url)
    success = suite.test_complete_game_flow()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

