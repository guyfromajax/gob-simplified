"""
Restore 2-3 Zone Defense to defenses_collection.

This script adds the 2-3 Zone defense back to the universal defenses collection
if it's missing. It uses the same structure as the original init script.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import defenses_collection

def restore_23_zone_defense():
    """Restore 2-3 Zone Defense to defenses_collection."""
    
    # Import zone definitions from shared_defense
    from BackEnd.utils.shared_defense import ZONE_23_NORMAL, ZONE_23_LOWER_SHIFT, ZONE_23_UPPER_SHIFT
    
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
        "defense_id": "2-3-zone",
        "defense_type": "Zone",
        "name": "2-3 Zone",
        "description": "Standard 2-3 zone defense with two guards up top and three players in the paint",
        "effectiveness": 0.0,  # Top-level field (not in stats)
        "game_stats": create_granular_stats(),
        "season_stats": create_granular_stats(),
        "zone_definitions": {
            "normal": ZONE_23_NORMAL,
            "lower_shift": ZONE_23_LOWER_SHIFT,
            "upper_shift": ZONE_23_UPPER_SHIFT
        },
        "shift_triggers": {
            "lower_shift": ["lower wing", "lower midCorner", "lower corner"],
            "upper_shift": ["upper wing", "upper midCorner", "upper corner"]
        }
    }
    
    print("Restoring 2-3 Zone Defense to defenses_collection...")
    
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
                "zone_definitions": defense["zone_definitions"],
                "shift_triggers": defense["shift_triggers"],
                "effectiveness": defense["effectiveness"]
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
        print(f"  Has zone_definitions: {added_defense.get('zone_definitions') is not None}")
        print(f"  Has shift_triggers: {added_defense.get('shift_triggers') is not None}")
    else:
        print("\n❌ Verification failed: Defense not found after insert/update")

if __name__ == "__main__":
    restore_23_zone_defense()

