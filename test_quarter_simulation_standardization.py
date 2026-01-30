#!/usr/bin/env python3
"""
Comprehensive test suite for all 9 quarter simulation scenarios.
Tests all combinations of game modes (Single Game, Franchise, Tournament) 
and buttons (Play Quarter, Sim To 4th Quarter, Sim Full Game).

This test verifies that our standardization fixes work correctly across all scenarios.
"""
import requests
import json
import time
from typing import Dict, Any


class QuarterSimulationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = {}
        
    def test_scenario(self, mode: str, button: str, description: str) -> Dict[str, Any]:
        """Test a specific scenario and return results."""
        print(f"\n🧪 Testing: {description}")
        print(f"   Mode: {mode}, Button: {button}")
        
        try:
            if mode == "single":
                return self._test_single_game(button)
            elif mode == "franchise":
                return self._test_franchise_mode(button)
            elif mode == "tournament":
                return self._test_tournament_mode(button)
            else:
                return {"success": False, "error": f"Unknown mode: {mode}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_single_game(self, button: str) -> Dict[str, Any]:
        """Test Single Game mode scenarios."""
        # Start a single game
        game_data = {
            "home_team": "Bentley-Truman",
            "away_team": "Lancaster",
            "quarter": 1,
            "home_lineup": {
                "PG": "f23fae35-ea45-44fe-a698-a06580707783",
                "SG": "f3f74388-9907-4e71-becd-05992f8ce5b2",
                "SF": "fa15e712-21f7-4e6f-951d-b5fb3bb45812",
                "PF": "8487cb3b-887b-472a-90d9-f46caa572d46",
                "C": "88ab7e7e-c3ef-4f45-ab85-0814891fddb8"
            },
            "away_lineup": {
                "PG": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "SG": "b2c3d4e5-f6g7-8901-bcde-f23456789012",
                "SF": "c3d4e5f6-g7h8-9012-cdef-345678901234",
                "PF": "d4e5f6g7-h8i9-0123-defg-456789012345",
                "C": "e5f6g7h8-i9j0-1234-efgh-567890123456"
            },
            "user_team_side": "home",
            "playcall_settings": {"Fast_Break_Entries": 50, "3-2 Motion": 30}
        }
        
        if button == "Play Quarter":
            # Test Play Quarter button
            response = requests.post(f"{self.base_url}/api/simulate-quarter", json=game_data)
            return self._analyze_response(response, "Play Quarter")
            
        elif button == "Sim To 4th Quarter":
            # Test Sim To 4th Quarter button - simulate Q1, Q2, Q3, then Q4
            results = []
            current_game_id = None
            for quarter in range(1, 5):
                if current_game_id:
                    game_data["game_id"] = current_game_id
                game_data["quarter"] = quarter
                response = requests.post(f"{self.base_url}/api/simulate-quarter", json=game_data)
                result = self._analyze_response(response, f"Sim To 4th Quarter Q{quarter}")
                results.append(result)
                if not result["success"]:
                    break
                # Extract game_id from successful response for next quarter
                if result.get("game_id"):
                    current_game_id = result["game_id"]
            return {"success": all(r["success"] for r in results), "details": results}
            
        elif button == "Sim Full Game":
            # Test Sim Full Game button (simulate all 4 quarters)
            results = []
            current_game_id = None
            for quarter in range(1, 5):
                if current_game_id:
                    game_data["game_id"] = current_game_id
                game_data["quarter"] = quarter
                response = requests.post(f"{self.base_url}/api/simulate-quarter", json=game_data)
                result = self._analyze_response(response, f"Sim Full Game Q{quarter}")
                results.append(result)
                if not result["success"]:
                    break
                # Extract game_id from successful response for next quarter
                if result.get("game_id"):
                    current_game_id = result["game_id"]
            return {"success": all(r["success"] for r in results), "details": results}
    
    def _test_franchise_mode(self, button: str) -> Dict[str, Any]:
        """Test Franchise mode scenarios."""
        # Create a franchise first
        franchise_data = {
            "team_name": "Bentley-Truman"
        }
        
        try:
            franchise_response = requests.post(f"{self.base_url}/franchise/select-team", json=franchise_data)
            if franchise_response.status_code != 200:
                return {"success": False, "error": f"Failed to create franchise: {franchise_response.status_code}"}
            
            franchise_id = franchise_response.json().get("franchise_id")
            if not franchise_id:
                return {"success": False, "error": "No franchise_id returned"}
            
            # Test franchise scenarios
            game_data = {
                "home_team": "Bentley-Truman",
                "away_team": "Lancaster",
                "quarter": 1,
                "franchise_id": franchise_id,
                "user_team_side": "home",
                "playcall_settings": {"Fast_Break_Entries": 50}
            }
            
            if button == "Play Quarter":
                response = requests.post(f"{self.base_url}/api/simulate-quarter", json=game_data)
                return self._analyze_response(response, "Franchise Play Quarter")
                
            elif button == "Sim To 4th Quarter":
                # Test Sim To 4th Quarter button - simulate Q1, Q2, Q3, then Q4
                results = []
                current_game_id = None
                for quarter in range(1, 5):
                    if current_game_id:
                        game_data["game_id"] = current_game_id
                    game_data["quarter"] = quarter
                    response = requests.post(f"{self.base_url}/api/simulate-quarter", json=game_data)
                    result = self._analyze_response(response, f"Franchise Sim To 4th Quarter Q{quarter}")
                    results.append(result)
                    if not result["success"]:
                        break
                    # Extract game_id from successful response for next quarter
                    if result.get("game_id"):
                        current_game_id = result["game_id"]
                return {"success": all(r["success"] for r in results), "details": results}
                
            elif button == "Sim Full Game":
                results = []
                current_game_id = None
                for quarter in range(1, 5):
                    if current_game_id:
                        game_data["game_id"] = current_game_id
                    game_data["quarter"] = quarter
                    response = requests.post(f"{self.base_url}/api/simulate-quarter", json=game_data)
                    result = self._analyze_response(response, f"Franchise Sim Full Game Q{quarter}")
                    results.append(result)
                    if not result["success"]:
                        break
                    # Extract game_id from successful response for next quarter
                    if result.get("game_id"):
                        current_game_id = result["game_id"]
                return {"success": all(r["success"] for r in results), "details": results}
                
        except Exception as e:
            return {"success": False, "error": f"Franchise test failed: {str(e)}"}
    
    def _test_tournament_mode(self, button: str) -> Dict[str, Any]:
        """Test Tournament mode scenarios."""
        try:
            # Start a tournament
            tournament_data = {
                "user_team_id": "Bentley-Truman"
            }
            
            tournament_response = requests.post(f"{self.base_url}/tournament/start", json=tournament_data)
            if tournament_response.status_code != 200:
                return {"success": False, "error": f"Failed to start tournament: {tournament_response.status_code}"}
            
            tournament_info = tournament_response.json()
            tournament_id = tournament_info.get("_id")
            if not tournament_id:
                return {"success": False, "error": "No tournament_id returned"}
            
            # Test tournament scenarios
            game_data = {
                "home_team": "Bentley-Truman",
                "away_team": "Lancaster",
                "quarter": 1,
                "tournament_id": tournament_id,
                "user_team_side": "home",
                "playcall_settings": {"Fast_Break_Entries": 50}
            }
            
            if button == "Play Quarter":
                response = requests.post(f"{self.base_url}/api/simulate-quarter", json=game_data)
                return self._analyze_response(response, "Tournament Play Quarter")
                
            elif button == "Sim To 4th Quarter":
                # Test Sim To 4th Quarter button - simulate Q1, Q2, Q3, then Q4
                results = []
                current_game_id = None
                for quarter in range(1, 5):
                    if current_game_id:
                        game_data["game_id"] = current_game_id
                    game_data["quarter"] = quarter
                    response = requests.post(f"{self.base_url}/api/simulate-quarter", json=game_data)
                    result = self._analyze_response(response, f"Tournament Sim To 4th Quarter Q{quarter}")
                    results.append(result)
                    if not result["success"]:
                        break
                    # Extract game_id from successful response for next quarter
                    if result.get("game_id"):
                        current_game_id = result["game_id"]
                return {"success": all(r["success"] for r in results), "details": results}
                
            elif button == "Sim Full Game":
                results = []
                current_game_id = None
                for quarter in range(1, 5):
                    if current_game_id:
                        game_data["game_id"] = current_game_id
                    game_data["quarter"] = quarter
                    response = requests.post(f"{self.base_url}/api/simulate-quarter", json=game_data)
                    result = self._analyze_response(response, f"Tournament Sim Full Game Q{quarter}")
                    results.append(result)
                    if not result["success"]:
                        break
                    # Extract game_id from successful response for next quarter
                    if result.get("game_id"):
                        current_game_id = result["game_id"]
                return {"success": all(r["success"] for r in results), "details": results}
                
        except Exception as e:
            return {"success": False, "error": f"Tournament test failed: {str(e)}"}
    
    def _analyze_response(self, response: requests.Response, test_name: str) -> Dict[str, Any]:
        """Analyze API response and return test results."""
        if response.status_code == 200:
            try:
                data = response.json()
                return {
                    "success": True,
                    "test_name": test_name,
                    "status_code": response.status_code,
                    "game_id": data.get("game_id"),
                    "quarter": data.get("quarter"),
                    "score": data.get("score", {}),
                    "message": "✅ Success"
                }
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "test_name": test_name,
                    "status_code": response.status_code,
                    "error": "Invalid JSON response",
                    "message": "❌ JSON Error"
                }
        else:
            return {
                "success": False,
                "test_name": test_name,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"❌ HTTP {response.status_code}"
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all 9 test scenarios."""
        print("🚀 Starting comprehensive quarter simulation tests...")
        print("=" * 60)
        
        scenarios = [
            ("single", "Play Quarter", "Single Game - Play Quarter"),
            ("single", "Sim To 4th Quarter", "Single Game - Sim To 4th Quarter"),
            ("single", "Sim Full Game", "Single Game - Sim Full Game"),
            ("franchise", "Play Quarter", "Franchise - Play Quarter"),
            ("franchise", "Sim To 4th Quarter", "Franchise - Sim To 4th Quarter"),
            ("franchise", "Sim Full Game", "Franchise - Sim Full Game"),
            ("tournament", "Play Quarter", "Tournament - Play Quarter"),
            ("tournament", "Sim To 4th Quarter", "Tournament - Sim To 4th Quarter"),
            ("tournament", "Sim Full Game", "Tournament - Sim Full Game"),
        ]
        
        results = {}
        passed = 0
        failed = 0
        
        for mode, button, description in scenarios:
            result = self.test_scenario(mode, button, description)
            results[f"{mode}_{button}"] = result
            
            if result["success"]:
                passed += 1
                print(f"   ✅ PASSED")
            else:
                failed += 1
                print(f"   ❌ FAILED: {result.get('error', 'Unknown error')}")
            
            time.sleep(0.5)  # Brief pause between tests
        
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {passed} passed, {failed} failed out of {len(scenarios)} total")
        
        if failed == 0:
            print("🎉 All tests passed! Standardization is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the details above.")
        
        return {
            "total_tests": len(scenarios),
            "passed": passed,
            "failed": failed,
            "success_rate": passed / len(scenarios),
            "results": results
        }


def main():
    """Run the comprehensive test suite."""
    tester = QuarterSimulationTester()
    results = tester.run_all_tests()
    
    # Save results to file
    with open("quarter_simulation_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: quarter_simulation_test_results.json")
    
    return results["success_rate"] == 1.0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
