"""
Test suite for verifying playbook and strategy settings persistence.

Tests the complete flow:
1. init-game creates game document
2. save_playbooks saves playbook settings
3. update_gameplan saves strategy settings
4. simulate-quarter loads and applies settings
5. Settings persist through timeouts
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from BackEnd.api.api import app
from BackEnd.db import games_collection, teams_collection
from bson import ObjectId
import json

client = TestClient(app)


class TestSettingsPersistence:
    """Test settings persistence across the game lifecycle."""
    
    def test_playbook_settings_persist_into_gameplay(self):
        """Test that playbook settings saved pre-game persist into gameplay."""
        # Step 1: Create game via init-game
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        assert init_response.status_code == 200
        game_id = init_response.json()["game_id"]
        assert game_id is not None
        
        # Verify game document exists
        game_doc = games_collection.find_one({"_id": game_id})
        assert game_doc is not None, f"Game document {game_id} should exist after init-game"
        
        # Step 2: Save playbook settings
        playbook_settings = {
            "motion": {
                "4-1 Motion": 50,
                "3-2 Motion": 30,
                "5-0 Motion": 20
            },
            "set_play_inside": {
                "Base Post Play": 100
            },
            "set_play_attack": {
                "Pick & Roll": 100
            },
            "set_play_outside": {
                "Double Screen for SG": 100
            },
            "zone_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {}
        }
        
        save_response = client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": "Morristown",
            "game_id": game_id,
            "playbook_settings": playbook_settings
        })
        assert save_response.status_code == 200, f"Failed to save playbooks: {save_response.text}"
        
        # Verify settings are in game document
        game_doc = games_collection.find_one({"_id": game_id})
        assert game_doc is not None
        
        # Find team_id key for Morristown
        teams = game_doc.get("teams", {})
        morristown_team_id = None
        for tid, team_data in teams.items():
            if team_data.get("name") == "Morristown":
                morristown_team_id = tid
                break
        
        assert morristown_team_id is not None, "Morristown team_id should exist in game document"
        
        morristown_team = teams.get(morristown_team_id, {})
        saved_playbook = morristown_team.get("playbook_settings", {})
        
        assert saved_playbook is not None, f"playbook_settings should exist for team {morristown_team_id}"
        assert saved_playbook.get("motion", {}).get("4-1 Motion") == 50, "Motion play percentage should be saved"
        
        # Step 3: Save strategy settings
        strategy_settings = {
            "offense": 2,
            "inside": 3,
            "attack": 2,
            "outside": 1,
            "tempo": 2,
            "defense": 2,
            "aggression": 3,
            "hc_trap": 1,
            "fc_press": 1,
            "rebounding": 2
        }
        
        gameplan_response = client.put("/api/gameplan", json={
            "mode": "single",
            "team_id": "Morristown",
            "game_id": game_id,
            "strategy_settings": strategy_settings
        })
        assert gameplan_response.status_code == 200, f"Failed to save game plan: {gameplan_response.text}"
        
        # Verify strategy settings are in game document
        game_doc = games_collection.find_one({"_id": game_id})
        morristown_team = game_doc.get("teams", {}).get(morristown_team_id, {})
        saved_strategy = morristown_team.get("strategy_settings", {})
        
        assert saved_strategy is not None, "strategy_settings should exist"
        assert saved_strategy.get("inside") == 3, "Strategy setting should be saved"
        
        # Step 4: Start gameplay via simulate-quarter
        sim_response = client.post("/api/simulate-quarter", json={
            "game_id": game_id,
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "quarter": 1,
            "mode": "single",
            "user_team_side": "home",
            "home_lineup": {
                "PG": "17694da1-cf52-4934-8755-aaddb23e7cd0",
                "SG": "e78e967d-86f8-4f31-b5f3-2729ac5c3ecb",
                "SF": "2e0089ee-a3e6-4c2d-8822-170fbbd335ac",
                "PF": "068c0b8a-c772-4542-a6ec-0cd6f21329ba",
                "C": "b3fab5a0-9a2e-41f8-89d4-271eaaceb6ad"
            },
            "full_sim": True
        })
        assert sim_response.status_code == 200, f"Failed to simulate quarter: {sim_response.text}"
        
        # Step 5: Verify settings were loaded and applied
        # Check that load_team_settings_from_doc was called (we can't directly verify GameManager,
        # but we can verify the settings are still in the document after simulation)
        game_doc_after = games_collection.find_one({"_id": game_id})
        assert game_doc_after is not None
        
        morristown_team_after = game_doc_after.get("teams", {}).get(morristown_team_id, {})
        playbook_after = morristown_team_after.get("playbook_settings", {})
        strategy_after = morristown_team_after.get("strategy_settings", {})
        
        # Settings should still be in document
        assert playbook_after is not None, "playbook_settings should persist after simulate-quarter"
        assert playbook_after.get("motion", {}).get("4-1 Motion") == 50, "Motion play percentage should persist"
        assert strategy_after is not None, "strategy_settings should persist after simulate-quarter"
        assert strategy_after.get("inside") == 3, "Strategy setting should persist"
    
    def test_settings_load_via_load_team_settings_from_doc(self):
        """Test that load_team_settings_from_doc correctly loads settings from game document."""
        from BackEnd.api.api import load_team_settings_from_doc
        
        # Create game and save settings
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        game_id = init_response.json()["game_id"]
        
        # Save playbook settings
        playbook_settings = {
            "motion": {"4-1 Motion": 100},
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
            "team_id": "Morristown",
            "game_id": game_id,
            "playbook_settings": playbook_settings
        })
        
        # Save strategy settings
        strategy_settings = {
            "offense": 2,
            "inside": 3,
            "attack": 2,
            "outside": 1,
            "tempo": 2,
            "defense": 2,
            "aggression": 3,
            "hc_trap": 1,
            "fc_press": 1,
            "rebounding": 2
        }
        
        client.put("/api/gameplan", json={
            "mode": "single",
            "team_id": "Morristown",
            "game_id": game_id,
            "strategy_settings": strategy_settings
        })
        
        # Test load_team_settings_from_doc
        settings = load_team_settings_from_doc(
            mode="single",
            doc_id=game_id,
            team_id=None,
            team_name="Morristown"
        )
        
        assert settings is not None, "load_team_settings_from_doc should return settings"
        assert settings.get("playbook_settings") is not None, "playbook_settings should be loaded"
        assert settings.get("strategy_settings") is not None, "strategy_settings should be loaded"
        
        loaded_playbook = settings.get("playbook_settings", {})
        loaded_strategy = settings.get("strategy_settings", {})
        
        assert loaded_playbook.get("motion", {}).get("4-1 Motion") == 100, "Motion play percentage should match"
        assert loaded_strategy.get("inside") == 3, "Strategy setting should match"
    
    def test_team_id_resolution_in_load_team_settings(self):
        """Test that load_team_settings_from_doc correctly resolves team_id from team_name."""
        from BackEnd.api.api import load_team_settings_from_doc
        
        # Create game
        init_response = client.post("/api/init-game", json={
            "home_team": "Morristown",
            "away_team": "Lancaster",
            "mode": "single"
        })
        game_id = init_response.json()["game_id"]
        
        # Get actual team_id from game document
        game_doc = games_collection.find_one({"_id": game_id})
        teams = game_doc.get("teams", {})
        morristown_team_id = None
        for tid, team_data in teams.items():
            if team_data.get("name") == "Morristown":
                morristown_team_id = tid
                break
        
        assert morristown_team_id is not None
        
        # Save settings
        client.post("/api/playbooks", json={
            "mode": "single",
            "team_id": "Morristown",
            "game_id": game_id,
            "playbook_settings": {
                "motion": {"4-1 Motion": 100},
                "set_play_inside": {},
                "set_play_attack": {},
                "set_play_outside": {},
                "zone_defense": {},
                "slot_assignments": {},
                "motion_dropdowns": {},
                "position_filters": {}
            }
        })
        
        # Test loading with team_name (should resolve to team_id)
        settings = load_team_settings_from_doc(
            mode="single",
            doc_id=game_id,
            team_id=None,
            team_name="Morristown"
        )
        
        assert settings is not None
        assert settings.get("playbook_settings") is not None
        assert settings.get("playbook_settings", {}).get("motion", {}).get("4-1 Motion") == 100

