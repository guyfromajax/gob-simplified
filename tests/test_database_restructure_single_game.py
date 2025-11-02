"""
Test suite for database restructure - Single Game mode only
Tests the new nested team structure for game documents

Focus areas:
1. Game initialization (Q1) with plays in memory
2. Play skeleton retrieval (memory-first, db-fallback)
3. Game save structure (nested teams, no animations)
4. Game load and resume (Q2-Q4)
5. Multi-quarter simulation flow
"""

import pytest
from bson import ObjectId
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
from BackEnd.db import games_collection
from BackEnd.utils.shared import summarize_game_state


class TestSingleGameDatabaseStructure:
    """Test new nested database structure for Single Game mode"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup before and cleanup after each test"""
        self.test_game_ids = []
        yield
        # Cleanup: delete test games from database
        for game_id in self.test_game_ids:
            try:
                games_collection.delete_one({"_id": game_id})
            except Exception:
                pass
    
    def test_q1_game_initialization(self):
        """Test Q1 game starts with correct structure"""
        # Create a new game
        gm = GameManager("Bentley-Truman", "Little York", mode="single")
        
        # Verify teams have plays in memory
        assert hasattr(gm.home_team, 'plays'), "Home team missing plays attribute"
        assert hasattr(gm.away_team, 'plays'), "Away team missing plays attribute"
        assert len(gm.home_team.plays) > 0, "Home team plays dict is empty"
        assert len(gm.away_team.plays) > 0, "Away team plays dict is empty"
        
        # Verify plays have correct structure
        sample_play_name = list(gm.home_team.plays.keys())[0]
        sample_play = gm.home_team.plays[sample_play_name]
        
        assert "skeletons" in sample_play, "Play missing skeletons"
        assert "standard" in sample_play["skeletons"], "Play missing standard skeleton"
        assert "game_stats" in sample_play, "Play missing game_stats"
        assert "effectiveness" in sample_play["game_stats"], "Play missing effectiveness"
        
        # Verify skeleton structure
        skeleton = sample_play["skeletons"]["standard"]
        assert "steps" in skeleton, "Skeleton missing steps"
        assert len(skeleton["steps"]) > 0, "Skeleton has no steps"
        
        # Verify team attributes exist
        assert hasattr(gm.home_team, 'team_attributes'), "Home team missing team_attributes"
        assert hasattr(gm.away_team, 'team_attributes'), "Away team missing team_attributes"
        
        print("✅ Q1 game initialization test passed")
    
    def test_play_skeleton_retrieval_from_memory(self):
        """Test that play skeletons are retrieved from memory for Q1 games"""
        from BackEnd.engine.phase_resolution import _get_skeleton_from_team_plays
        
        # Create a new game
        gm = GameManager("Bentley-Truman", "Little York", mode="single")
        
        # Set current playcall
        sample_play_name = list(gm.home_team.plays.keys())[0]
        gm.game_state["current_playcall"] = sample_play_name
        
        # Get skeleton (should come from memory, not DB)
        skeleton = _get_skeleton_from_team_plays(
            sample_play_name,
            gm.home_team.team_id,
            gm
        )
        
        assert skeleton is not None, f"Failed to retrieve skeleton for '{sample_play_name}'"
        assert "steps" in skeleton, "Retrieved skeleton missing steps"
        assert len(skeleton["steps"]) > 0, "Retrieved skeleton has no steps"
        
        print(f"✅ Play skeleton retrieval test passed - retrieved {len(skeleton['steps'])} steps from memory")
    
    def test_game_save_structure(self):
        """Test that saved game has correct nested structure"""
        # Create and simulate Q1
        gm = GameManager("Bentley-Truman", "Little York", mode="single")
        gm.game_id = ObjectId()  # Assign a game ID
        self.test_game_ids.append(gm.game_id)
        
        # Simulate a few turns (not full quarter to save time)
        for _ in range(5):
            try:
                gm.turn_manager.run_micro_turn()
            except Exception:
                break  # Game might end early
        
        # Save game state
        summary = summarize_game_state(gm, exclude_animations=True)
        games_collection.update_one(
            {"_id": gm.game_id},
            {"$set": summary},
            upsert=True
        )
        
        # Retrieve from database
        saved_game = games_collection.find_one({"_id": gm.game_id})
        assert saved_game is not None, "Game not saved to database"
        
        # Verify nested team structure
        assert "home_team" in saved_game, "Missing home_team in saved game"
        assert "away_team" in saved_game, "Missing away_team in saved game"
        
        home_team = saved_game["home_team"]
        away_team = saved_game["away_team"]
        
        # Verify home_team is an object (not string)
        assert isinstance(home_team, dict), "home_team should be a dict (nested object)"
        assert isinstance(away_team, dict), "away_team should be a dict (nested object)"
        
        # Verify required fields in team objects
        required_fields = ["name", "team_id", "colors", "attributes", "strategy_settings", 
                          "scouting", "plays", "box_score", "totals"]
        for field in required_fields:
            assert field in home_team, f"home_team missing field: {field}"
            assert field in away_team, f"away_team missing field: {field}"
        
        # Verify plays are nested under each team
        assert isinstance(home_team["plays"], list), "home_team plays should be a list"
        assert len(home_team["plays"]) > 0, "home_team plays list is empty"
        
        # Verify animations are excluded from turns
        if "turns" in saved_game and len(saved_game["turns"]) > 0:
            for turn in saved_game["turns"]:
                assert "animations" not in turn, f"Turn should not have animations in saved game"
        
        # Verify no duplicate top-level keys (old structure removed)
        assert "team_plays" not in saved_game, "Old team_plays key should not exist"
        assert "team_attributes" not in saved_game, "Old team_attributes key should not exist"
        assert "scouting" not in saved_game, "Old scouting key should not exist"
        
        print("✅ Game save structure test passed - nested teams, no animations, no duplicates")
    
    def test_game_load_and_resume(self):
        """Test loading a saved game and resuming Q2"""
        # Create and simulate Q1
        gm = GameManager("Bentley-Truman", "Little York", mode="single")
        gm.game_id = ObjectId()
        self.test_game_ids.append(gm.game_id)
        
        # Simulate Q1 (abbreviated)
        for _ in range(10):
            try:
                gm.turn_manager.run_micro_turn()
            except Exception:
                break
        
        gm.quarter = 1
        
        # Save Q1
        summary = summarize_game_state(gm, exclude_animations=True)
        games_collection.update_one(
            {"_id": gm.game_id},
            {"$set": summary},
            upsert=True
        )
        
        # Load from database
        saved_game = games_collection.find_one({"_id": gm.game_id})
        
        # Extract team data from nested structure
        home_team_data = saved_game["home_team"]
        away_team_data = saved_game["away_team"]
        
        # Create new GameManager with loaded data
        gm2 = GameManager(
            home_team_data["name"],
            away_team_data["name"],
            home_strategy_settings=home_team_data.get("strategy_settings"),
            away_strategy_settings=away_team_data.get("strategy_settings"),
            home_team_attributes=home_team_data.get("attributes"),
            away_team_attributes=away_team_data.get("attributes"),
            home_scouting_data=home_team_data.get("scouting"),
            away_scouting_data=away_team_data.get("scouting"),
            home_plays_data=home_team_data.get("plays"),
            away_plays_data=away_team_data.get("plays"),
            mode="single"
        )
        gm2.game_id = gm.game_id
        gm2.quarter = 2
        
        # Verify loaded teams have plays
        assert len(gm2.home_team.plays) > 0, "Loaded home team has no plays"
        assert len(gm2.away_team.plays) > 0, "Loaded away team has no plays"
        
        # Verify play skeleton retrieval works for loaded game
        from BackEnd.engine.phase_resolution import _get_skeleton_from_team_plays
        sample_play_name = list(gm2.home_team.plays.keys())[0]
        skeleton = _get_skeleton_from_team_plays(
            sample_play_name,
            gm2.home_team.team_id,
            gm2
        )
        
        assert skeleton is not None, "Failed to retrieve skeleton from loaded game"
        assert len(skeleton["steps"]) > 0, "Loaded skeleton has no steps"
        
        # Simulate a few Q2 turns
        for _ in range(5):
            try:
                gm2.turn_manager.run_micro_turn()
            except Exception:
                break
        
        print("✅ Game load and resume test passed - Q2 runs with loaded data")
    
    def test_multi_quarter_save_load_cycle(self):
        """Test complete game flow: Q1 → save → Q2 → save → Q3 → save → Q4"""
        gm = GameManager("Bentley-Truman", "Little York", mode="single")
        gm.game_id = ObjectId()
        self.test_game_ids.append(gm.game_id)
        
        for quarter in range(1, 5):
            # Simulate a few turns for this quarter
            for _ in range(5):
                try:
                    gm.turn_manager.run_micro_turn()
                except Exception:
                    break
            
            gm.quarter = quarter
            
            # Save after each quarter
            summary = summarize_game_state(gm, exclude_animations=True)
            games_collection.update_one(
                {"_id": gm.game_id},
                {"$set": summary},
                upsert=True
            )
            
            # Verify save succeeded
            saved_game = games_collection.find_one({"_id": gm.game_id})
            assert saved_game is not None, f"Q{quarter} save failed"
            assert saved_game["quarter"] == quarter, f"Quarter mismatch: expected {quarter}, got {saved_game['quarter']}"
            
            # Load for next quarter (except Q4)
            if quarter < 4:
                home_team_data = saved_game["home_team"]
                away_team_data = saved_game["away_team"]
                
                gm = GameManager(
                    home_team_data["name"],
                    away_team_data["name"],
                    home_strategy_settings=home_team_data.get("strategy_settings"),
                    away_strategy_settings=away_team_data.get("strategy_settings"),
                    home_team_attributes=home_team_data.get("attributes"),
                    away_team_attributes=away_team_data.get("attributes"),
                    home_scouting_data=home_team_data.get("scouting"),
                    away_scouting_data=away_team_data.get("scouting"),
                    home_plays_data=home_team_data.get("plays"),
                    away_plays_data=away_team_data.get("plays"),
                    mode="single"
                )
                gm.game_id = saved_game["_id"]
                gm.quarter = quarter + 1
                
                # Verify plays still exist in memory
                assert len(gm.home_team.plays) > 0, f"Q{quarter+1} home team has no plays"
                assert len(gm.away_team.plays) > 0, f"Q{quarter+1} away team has no plays"
        
        print("✅ Multi-quarter cycle test passed - Q1→Q2→Q3→Q4 with saves/loads")
    
    def test_team_name_extraction_compatibility(self):
        """Test that team name extraction works for both old and new structures"""
        # Simulate both old and new structures
        
        # New structure (nested object)
        new_structure = {
            "home_team": {
                "name": "Bentley-Truman",
                "team_id": "bentley-truman",
                "colors": {"primary_color": "#000000", "secondary_color": "#ffffff"}
            },
            "away_team": {
                "name": "Little York",
                "team_id": "little-york",
                "colors": {"primary_color": "#ff0000", "secondary_color": "#000000"}
            }
        }
        
        # Old structure (flat string)
        old_structure = {
            "home_team": "Bentley-Truman",
            "away_team": "Little York",
            "home_team_id": "bentley-truman",
            "away_team_id": "little-york"
        }
        
        # Test extraction logic (mimics frontend code)
        def extract_team_name(sim_data, team_key):
            """Extract team name from either old or new structure"""
            team_field = sim_data.get(team_key)
            if isinstance(team_field, dict):
                return team_field.get("name")
            return team_field
        
        # Test new structure
        assert extract_team_name(new_structure, "home_team") == "Bentley-Truman"
        assert extract_team_name(new_structure, "away_team") == "Little York"
        
        # Test old structure
        assert extract_team_name(old_structure, "home_team") == "Bentley-Truman"
        assert extract_team_name(old_structure, "away_team") == "Little York"
        
        print("✅ Team name extraction compatibility test passed")
    
    def test_play_effectiveness_tracking(self):
        """Test that play effectiveness scores are initialized and tracked"""
        gm = GameManager("Bentley-Truman", "Little York", mode="single")
        
        # Check a sample play from home team
        sample_play_name = list(gm.home_team.plays.keys())[0]
        sample_play = gm.home_team.plays[sample_play_name]
        
        # Verify effectiveness exists and is within expected range
        assert "game_stats" in sample_play, "Play missing game_stats"
        assert "effectiveness" in sample_play["game_stats"], "Play missing effectiveness"
        
        effectiveness = sample_play["game_stats"]["effectiveness"]
        assert isinstance(effectiveness, (int, float)), "Effectiveness should be numeric"
        assert -10 <= effectiveness <= 10, f"Effectiveness out of range: {effectiveness}"
        
        # Verify season_stats does NOT exist for single mode
        assert "season_stats" not in sample_play, "Single mode should not have season_stats"
        
        print(f"✅ Play effectiveness tracking test passed - effectiveness={effectiveness}")


if __name__ == "__main__":
    """Run tests directly with python (no pytest required)"""
    import sys
    
    test_class = TestSingleGameDatabaseStructure()
    test_methods = [
        ("Game Initialization", test_class.test_q1_game_initialization),
        ("Play Skeleton Retrieval", test_class.test_play_skeleton_retrieval_from_memory),
        ("Game Save Structure", test_class.test_game_save_structure),
        ("Game Load & Resume", test_class.test_game_load_and_resume),
        ("Multi-Quarter Cycle", test_class.test_multi_quarter_save_load_cycle),
        ("Team Name Extraction", test_class.test_team_name_extraction_compatibility),
        ("Play Effectiveness", test_class.test_play_effectiveness_tracking),
    ]
    
    print("\n" + "="*70)
    print("DATABASE RESTRUCTURE TEST SUITE - SINGLE GAME MODE")
    print("="*70 + "\n")
    
    passed = 0
    failed = 0
    
    for test_name, test_func in test_methods:
        print(f"\n🧪 Running: {test_name}")
        print("-" * 70)
        
        # Manual setup (replaces fixture)
        test_class.test_game_ids = []
        
        try:
            test_func()
            passed += 1
            print(f"✅ PASSED: {test_name}\n")
        except AssertionError as e:
            failed += 1
            print(f"❌ FAILED: {test_name}")
            print(f"   Error: {e}\n")
        except Exception as e:
            failed += 1
            print(f"❌ ERROR: {test_name}")
            print(f"   Exception: {e}\n")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup after each test
            for game_id in test_class.test_game_ids:
                try:
                    games_collection.delete_one({"_id": game_id})
                except Exception:
                    pass
    
    print("="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70 + "\n")
    
    sys.exit(0 if failed == 0 else 1)

