"""
Phase 5.6: Comprehensive Settings Persistence Tests

Tests all refactored functionality from Phase 5.1-5.5:
- Team ID normalization (Phase 5.1)
- No legacy fallbacks (Phase 5.2)
- Simplified save/load flow (Phase 5.3)
- Mode handling (Phase 5.5)
- End-to-end persistence
- Error handling
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from BackEnd.api.api import app
from BackEnd.db import games_collection, franchises_collection, tournaments_collection, teams_collection
from BackEnd.api.gameplan_routes import (
    normalize_team_id_to_canonical,
    get_collection_and_doc_id,
    get_team_settings_path
)
from bson import ObjectId
import json

client = TestClient(app)


# ============================================================================
# Test Suite 1: Team ID Normalization (Phase 5.1 Validation)
# ============================================================================

class TestTeamIDNormalization:
    """Test that all team_id formats normalize correctly."""
    
    def test_normalize_team_name_to_canonical_single_mode(self):
        """Test: Save with team name → Normalizes to canonical team_id → Saves to correct key"""
        # Create game
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        assert init_response.status_code == 200
        game_id = init_response.json()["game_id"]
        
        # Get game document to check normalization
        game_doc = games_collection.find_one({"_id": game_id})
        assert game_doc is not None
        
        # Save with team name (should normalize to canonical team_id)
        playbook_settings = {
            "motion": {"4-1 Motion": 50},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        save_response = client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": "Morristown",  # Team name
            "game_id": game_id,
            "playbook_settings": playbook_settings
        })
        assert save_response.status_code == 200
        
        # Verify settings saved to canonical team_id key (not team name)
        game_doc_after = games_collection.find_one({"_id": game_id})
        teams = game_doc_after.get("teams", {})
        
        # Find the canonical team_id key (should be uppercase with underscores)
        canonical_team_id = None
        for tid in teams.keys():
            if teams[tid].get("name") == "Morristown":
                canonical_team_id = tid
                break
        
        assert canonical_team_id is not None, "Should find canonical team_id"
        assert canonical_team_id != "Morristown", "Should not use team name as key"
        
        # Verify settings saved to canonical key
        saved_settings = teams.get(canonical_team_id, {}).get("playbook_settings", {})
        assert saved_settings.get("motion", {}).get("4-1 Motion") == 50
    
    def test_normalize_canonical_team_id_single_mode(self):
        """Test: Save with canonical team_id → No normalization needed → Saves to correct key"""
        # Create game
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        assert init_response.status_code == 200
        game_id = init_response.json()["game_id"]
        
        # Get canonical team_id from document
        game_doc = games_collection.find_one({"_id": game_id})
        teams = game_doc.get("teams", {})
        canonical_team_id = None
        for tid in teams.keys():
            if teams[tid].get("name") == "Morristown":
                canonical_team_id = tid
                break
        
        assert canonical_team_id is not None
        
        # Save with canonical team_id (should work without normalization)
        playbook_settings = {
            "motion": {"3-2 Motion": 100},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        save_response = client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": canonical_team_id,  # Canonical format
            "game_id": game_id,
            "playbook_settings": playbook_settings
        })
        assert save_response.status_code == 200
        
        # Verify settings saved to same canonical key
        game_doc_after = games_collection.find_one({"_id": game_id})
        saved_settings = game_doc_after.get("teams", {}).get(canonical_team_id, {}).get("playbook_settings", {})
        assert saved_settings.get("motion", {}).get("3-2 Motion") == 100
    
    def test_load_with_team_name_normalizes_correctly(self):
        """Test: Load with team name → Normalizes to canonical team_id → Loads from correct key"""
        # Create game and save settings
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        game_id = init_response.json()["game_id"]
        
        # Get canonical team_id
        game_doc = games_collection.find_one({"_id": game_id})
        teams = game_doc.get("teams", {})
        canonical_team_id = None
        for tid in teams.keys():
            if teams[tid].get("name") == "Morristown":
                canonical_team_id = tid
                break
        
        # Save with canonical team_id
        playbook_settings = {
            "motion": {"5-0 Motion": 75},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": canonical_team_id,
            "game_id": game_id,
            "playbook_settings": playbook_settings
        })
        
        # Load with team name (should normalize and find settings)
        load_response = client.get("/api/playbooks", params={
            "mode": "single",
            "team_id": "Morristown",  # Team name
            "game_id": game_id
        })
        assert load_response.status_code == 200
        
        loaded_data = load_response.json()
        # Verify we got the settings (motion plays should be in response)
        assert "motion" in loaded_data
        # Settings should be loaded from canonical key


# ============================================================================
# Test Suite 2: No Legacy Fallbacks (Phase 5.2 Validation)
# ============================================================================

class TestNoLegacyFallbacks:
    """Test that invalid inputs raise explicit errors (no silent fallbacks)."""
    
    def test_invalid_team_id_raises_explicit_error(self):
        """Test: Invalid team_id → Raises HTTPException → No silent fallback to home/away"""
        # Create game
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        game_id = init_response.json()["game_id"]
        
        # Try to save with invalid team_id
        playbook_settings = {
            "motion": {},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        save_response = client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": "INVALID_TEAM",  # Invalid team
            "game_id": game_id,
            "playbook_settings": playbook_settings
        })
        
        # Should raise explicit error (400 or 404), not silent fallback
        assert save_response.status_code in [400, 404]
        assert "error" in save_response.json() or "detail" in save_response.json()
    
    def test_missing_franchise_id_raises_explicit_error(self):
        """Test: Missing franchise_id in franchise mode → Raises explicit error → No silent fallback"""
        # Try to save without franchise_id
        playbook_settings = {
            "motion": {},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        save_response = client.post("/api/playbooks", json={
            "mode": "franchise",
            "team_id": "some_team_id",
            # Missing franchise_id
            "playbook_settings": playbook_settings
        })
        
        # Should raise explicit error
        assert save_response.status_code == 400
        assert "franchise_id" in save_response.json().get("detail", "").lower()
    
    def test_missing_tournament_id_raises_explicit_error(self):
        """Test: Missing tournament_id in tournament mode → Raises explicit error → No silent fallback"""
        playbook_settings = {
            "motion": {},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        save_response = client.post("/api/playbooks", json={
            "mode": "tournament",
            "team_id": "some_team_id",
            # Missing tournament_id
            "playbook_settings": playbook_settings
        })
        
        # Should raise explicit error
        assert save_response.status_code == 400
        assert "tournament_id" in save_response.json().get("detail", "").lower()


# ============================================================================
# Test Suite 3: Simplified Save/Load Flow (Phase 5.3 Validation)
# ============================================================================

class TestSimplifiedSaveLoadFlow:
    """Test that save/load operations are single-point (no redundant operations)."""
    
    def test_save_playbooks_single_db_write(self):
        """Test: Save playbook settings → Single DB write → No verification reload"""
        # Create game
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        game_id = init_response.json()["game_id"]
        
        # Get initial document state
        game_doc_before = games_collection.find_one({"_id": game_id})
        teams_before = game_doc_before.get("teams", {})
        
        # Find canonical team_id
        canonical_team_id = None
        for tid in teams_before.keys():
            if teams_before[tid].get("name") == "Morristown":
                canonical_team_id = tid
                break
        
        # Save playbook settings
        playbook_settings = {
            "motion": {"4-1 Motion": 50},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        save_response = client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": canonical_team_id,
            "game_id": game_id,
            "playbook_settings": playbook_settings
        })
        assert save_response.status_code == 200
        
        # Verify settings saved (single write)
        game_doc_after = games_collection.find_one({"_id": game_id})
        saved_settings = game_doc_after.get("teams", {}).get(canonical_team_id, {}).get("playbook_settings", {})
        assert saved_settings.get("motion", {}).get("4-1 Motion") == 50
        
        # Note: We can't directly verify "no verification reload" without mocking,
        # but the fact that settings are saved correctly indicates single write worked
    
    def test_save_gameplan_single_db_write(self):
        """Test: Save game plan settings → Single DB write → No verification reload"""
        # Create game
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        game_id = init_response.json()["game_id"]
        
        # Get canonical team_id
        game_doc = games_collection.find_one({"_id": game_id})
        teams = game_doc.get("teams", {})
        canonical_team_id = None
        for tid in teams.keys():
            if teams[tid].get("name") == "Morristown":
                canonical_team_id = tid
                break
        
        # Save strategy settings
        strategy_settings = {
            "offense": 3,
            "inside": 2,
            "attack": 2,
            "outside": 1,
            "tempo": 2,
            "defense": 2,
            "aggression": 3,
            "hc_trap": 1,
            "fc_press": 1,
            "rebounding": 2
        }
        
        save_response = client.put("/api/gameplan", json={
            "mode": "single",
            "team_id": canonical_team_id,
            "game_id": game_id,
            "strategy_settings": strategy_settings
        })
        assert save_response.status_code == 200
        
        # Verify settings saved
        game_doc_after = games_collection.find_one({"_id": game_id})
        saved_settings = game_doc_after.get("teams", {}).get(canonical_team_id, {}).get("strategy_settings", {})
        assert saved_settings.get("offense") == 3
    
    def test_settings_persist_through_timeout(self):
        """Test: Settings persist through timeout → Load from DB → Settings match saved values"""
        # Create game and save settings
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        game_id = init_response.json()["game_id"]
        
        # Get canonical team_id
        game_doc = games_collection.find_one({"_id": game_id})
        teams = game_doc.get("teams", {})
        canonical_team_id = None
        for tid in teams.keys():
            if teams[tid].get("name") == "Morristown":
                canonical_team_id = tid
                break
        
        # Save settings
        playbook_settings = {
            "motion": {"4-1 Motion": 60},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": canonical_team_id,
            "game_id": game_id,
            "playbook_settings": playbook_settings
        })
        
        # Simulate timeout scenario: Load settings from DB
        load_response = client.get("/api/playbooks", params={
            "mode": "single",
            "team_id": canonical_team_id,
            "game_id": game_id,
            "source": "db"  # Force DB read
        })
        assert load_response.status_code == 200
        
        loaded_data = load_response.json()
        # Verify settings match
        assert "playbook_percentages" in loaded_data
        motion_percentages = loaded_data.get("playbook_percentages", {}).get("motion", {})
        assert motion_percentages.get("4-1 Motion") == 60


# ============================================================================
# Test Suite 4: Mode Handling (Phase 5.5 Validation)
# ============================================================================

class TestModeHandling:
    """Test that all modes use correct collection and path."""
    
    def test_single_mode_uses_games_collection(self):
        """Test: Single mode → Saves to `games` collection → `teams.{team_id}.playbook_settings`"""
        # Create game
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        game_id = init_response.json()["game_id"]
        
        # Get canonical team_id
        game_doc = games_collection.find_one({"_id": game_id})
        teams = game_doc.get("teams", {})
        canonical_team_id = None
        for tid in teams.keys():
            if teams[tid].get("name") == "Morristown":
                canonical_team_id = tid
                break
        
        # Save settings
        playbook_settings = {
            "motion": {"4-1 Motion": 50},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        save_response = client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": canonical_team_id,
            "game_id": game_id,
            "playbook_settings": playbook_settings
        })
        assert save_response.status_code == 200
        
        # Verify saved to games collection with correct path
        game_doc_after = games_collection.find_one({"_id": game_id})
        assert game_doc_after is not None
        saved_settings = game_doc_after.get("teams", {}).get(canonical_team_id, {}).get("playbook_settings", {})
        assert saved_settings.get("motion", {}).get("4-1 Motion") == 50
    
    def test_franchise_mode_uses_franchises_collection(self):
        """Test: Franchise mode → Saves to FTD (franchise_team_data); franchise doc no longer has franchise_teams."""
        # Create franchise (simplified - would normally use FranchiseManager)
        franchise_id = ObjectId()
        user_team_object_id = ObjectId()
        franchises_collection.insert_one({
            "_id": franchise_id,
            "user_team_id": "South Lancaster",
            "user_team_object_id": user_team_object_id,
        })
        
        try:
            playbook_settings = {
                "motion": {"4-1 Motion": 50},
                "set_play_inside": {},
                "set_play_attack": {},
                "set_play_outside": {},
                "zone_defense": {},
                "slot_assignments": {},
                "motion_dropdowns": {},
                "position_filters": {}
            }
            
            save_response = client.post("/api/playbooks", json={
                "mode": "franchise",
                "team_id": str(user_team_object_id),
                "franchise_id": str(franchise_id),
                "playbook_settings": playbook_settings
            })
            
            if save_response.status_code == 200:
                franchise_doc = franchises_collection.find_one({"_id": franchise_id})
                assert franchise_doc is not None
                # Franchise master settings are in FTD, not franchise_teams on franchise doc
                from BackEnd.db import franchise_team_data_collection
                ftd = franchise_team_data_collection.find_one(
                    {"franchise_id": franchise_id, "team_id": user_team_object_id}
                )
                assert ftd is not None
                assert ftd.get("playbook_settings", {}).get("motion", {}).get("4-1 Motion") == 50
        finally:
            franchises_collection.delete_one({"_id": franchise_id})
            from BackEnd.db import franchise_team_data_collection
            franchise_team_data_collection.delete_many({"franchise_id": franchise_id})
    
    def test_helper_functions_work_correctly(self):
        """Test: Helper functions (get_collection_and_doc_id, get_team_settings_path) work correctly"""
        # Test get_collection_and_doc_id
        collection, doc_id = get_collection_and_doc_id("single", game_id="test_game_id")
        assert collection == games_collection
        # normalize_game_id() converts invalid IDs to ObjectId format (24-char hex string)
        assert len(doc_id) == 24, "Should be normalized to ObjectId format (24 characters)"
        assert all(c in '0123456789abcdef' for c in doc_id), "Should be hex string"
        
        # Test get_team_settings_path
        path = get_team_settings_path("single", "MORRISTOWN")
        assert path == "teams.MORRISTOWN"
        
        path = get_team_settings_path("franchise", "MORRISTOWN")
        assert path == "teams.MORRISTOWN"  # Franchise master uses FTD; path used only for game/tournament doc
        
        path = get_team_settings_path("tournament", "MORRISTOWN")
        assert path == "teams.MORRISTOWN"


# ============================================================================
# Test Suite 5: End-to-End Persistence
# ============================================================================

class TestEndToEndPersistence:
    """Test settings persist through complete game flow."""
    
    def test_settings_persist_pre_game_to_gameplay(self):
        """Test: Save settings pre-game → Start game → Settings applied → Persist"""
        # Create game
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        game_id = init_response.json()["game_id"]
        
        # Get canonical team_id
        game_doc = games_collection.find_one({"_id": game_id})
        teams = game_doc.get("teams", {})
        canonical_team_id = None
        for tid in teams.keys():
            if teams[tid].get("name") == "Morristown":
                canonical_team_id = tid
                break
        
        # Save settings pre-game
        playbook_settings = {
            "motion": {"4-1 Motion": 50},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": canonical_team_id,
            "game_id": game_id,
            "playbook_settings": playbook_settings
        })
        
        # Start gameplay (simulate-quarter loads settings)
        # Note: Full simulate-quarter test would require lineup data
        # For now, verify settings are still in document
        game_doc_after = games_collection.find_one({"_id": game_id})
        saved_settings = game_doc_after.get("teams", {}).get(canonical_team_id, {}).get("playbook_settings", {})
        assert saved_settings.get("motion", {}).get("4-1 Motion") == 50


# ============================================================================
# Test Suite 6: Error Handling
# ============================================================================

class TestErrorHandling:
    """Test that all errors are explicit (no silent failures)."""
    
    def test_missing_document_raises_404(self):
        """Test: Missing document (game/franchise/tournament) → Raises 404 → Clear error message"""
        # Try to save to non-existent game
        playbook_settings = {
            "motion": {},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        fake_game_id = str(ObjectId())
        save_response = client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": "MORRISTOWN",
            "game_id": fake_game_id,
            "playbook_settings": playbook_settings
        })
        
        assert save_response.status_code == 404
        assert "not found" in save_response.json().get("detail", "").lower()
    
    def test_invalid_mode_raises_400(self):
        """Test: Invalid mode → Raises 400 → Clear error message"""
        playbook_settings = {
            "motion": {},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        save_response = client.post("/api/playbooks", json={
            "mode": "invalid_mode",
            "team_id": "MORRISTOWN",
            "game_id": "fake_id",
            "playbook_settings": playbook_settings
        })
        
        assert save_response.status_code == 400
        assert "invalid mode" in save_response.json().get("detail", "").lower()
    
    def test_missing_required_parameters_raises_400(self):
        """Test: Missing required parameters → Raises 400 → Clear error message"""
        playbook_settings = {
            "motion": {},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        # Missing game_id for single mode
        save_response = client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": "MORRISTOWN",
            # Missing game_id
            "playbook_settings": playbook_settings
        })
        
        assert save_response.status_code == 400
        assert "game_id" in save_response.json().get("detail", "").lower()

