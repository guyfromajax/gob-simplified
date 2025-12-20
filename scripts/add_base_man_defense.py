"""
Add Base Man Defense to the defenses_collection in MongoDB.

This script adds the Base Man defense definition with:
- defense_id, defense_type, name, description
- effectiveness (top-level field)
- cloaking (top-level field)
- game_stats, season_stats (usage and success tracking)
- zone_definitions: None (not applicable for Man defense)
- shift_triggers: None (not applicable for Man defense)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import defenses_collection

def add_base_man_defense():
    """Add Base Man Defense to defenses_collection."""
    
    # Helper function to create granular stats structure
    def create_granular_stats():
        return {
            "used": 0,
            "success": 0,
            "vs_motion": {"attempts": 0, "success": 0},
            "vs_set": {"attempts": 0, "success": 0},
            "vs_inside": {"attempts": 0, "success": 0},
            "vs_attack": {"attempts": 0, "success": 0},
            "vs_outside": {"attempts": 0, "success": 0},
            "vs_motion_inside": {"attempts": 0, "success": 0},
            "vs_motion_attack": {"attempts": 0, "success": 0},
            "vs_motion_outside": {"attempts": 0, "success": 0},
            "vs_set_inside": {"attempts": 0, "success": 0},
            "vs_set_attack": {"attempts": 0, "success": 0},
            "vs_set_outside": {"attempts": 0, "success": 0}
        }
    
    defense = {
        "defense_id": "base-man",
        "defense_type": "Man",
        "name": "Base Man",
        "description": "Standard man defense",
        "effectiveness": 0,
        "cloaking": 0,
        "game_stats": create_granular_stats(),
        "season_stats": create_granular_stats(),
        "zone_definitions": None,  # Not applicable for Man defense
        "shift_triggers": None  # Not applicable for Man defense
    }
    
    print("Adding Base Man Defense to defenses_collection...")
    
    # Check if defense already exists
    existing = defenses_collection.find_one({"defense_id": defense["defense_id"]})
    if existing:
        print(f"  ⚠️  Defense '{defense['name']}' already exists, updating...")
        # Update existing defense (preserve any stats that might exist)
        defenses_collection.update_one(
            {"defense_id": defense["defense_id"]},
            {"$set": {
                "name": defense["name"],
                "description": defense["description"],
                "defense_type": defense["defense_type"],
                "effectiveness": defense["effectiveness"],
                "cloaking": defense["cloaking"],
                "zone_definitions": defense["zone_definitions"],
                "shift_triggers": defense["shift_triggers"]
            },
             "$setOnInsert": {
                "game_stats": defense["game_stats"],
                "season_stats": defense["season_stats"]
            }}
        )
        print(f"  ✅ Updated: {defense['name']} (defense_id: {defense['defense_id']})")
    else:
        result = defenses_collection.insert_one(defense)
        print(f"  ✅ Inserted: {defense['name']} (defense_id: {defense['defense_id']})")
    
    # Verify
    added_defense = defenses_collection.find_one({"defense_id": defense["defense_id"]})
    if added_defense:
        print(f"\n✅ Verification successful:")
        print(f"  Defense ID: {added_defense['defense_id']}")
        print(f"  Name: {added_defense['name']}")
        print(f"  Type: {added_defense['defense_type']}")
        print(f"  Effectiveness: {added_defense.get('effectiveness', 0)}")
        print(f"  Cloaking: {added_defense.get('cloaking', 0)}")
        print(f"  Has game_stats: {added_defense.get('game_stats') is not None}")
        print(f"  Has season_stats: {added_defense.get('season_stats') is not None}")
        print(f"  zone_definitions: {added_defense.get('zone_definitions')}")
        print(f"  shift_triggers: {added_defense.get('shift_triggers')}")
    else:
        print("\n❌ Verification failed: Defense not found after insert/update")

if __name__ == "__main__":
    add_base_man_defense()

