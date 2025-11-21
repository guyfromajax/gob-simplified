"""
Add 3-2 Zone Defense to the defenses_collection in MongoDB.

This script adds the 3-2 zone defense definition with:
- defense_id, defense_type, name, description
- effectiveness (top-level field)
- game_stats, season_stats (usage and success tracking)
- zone_definitions (normal, lower_shift, upper_shift)
- shift_triggers (which spots trigger shifts)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import defenses_collection

def add_32_zone_defense():
    """Add 3-2 Zone Defense to defenses_collection."""
    
    # Import zone definitions from shared_defense
    from BackEnd.utils.shared_defense import ZONE_32_NORMAL, ZONE_32_LOWER_SHIFT, ZONE_32_UPPER_SHIFT
    
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
        "defense_id": "3-2-zone",
        "defense_type": "Zone",
        "name": "3-2 Zone",
        "description": "3-2 zone defense with three guards up top and two players in the paint",
        "effectiveness": 0.0,  # Top-level field (not in stats)
        "game_stats": create_granular_stats(),
        "season_stats": create_granular_stats(),
        "zone_definitions": {
            "normal": ZONE_32_NORMAL,
            "lower_shift": ZONE_32_LOWER_SHIFT,
            "upper_shift": ZONE_32_UPPER_SHIFT
        },
        "shift_triggers": {
            "lower_shift": ["lower corner"],
            "upper_shift": ["upper corner"]
        }
    }
    
    print("Adding 3-2 Zone Defense to defenses_collection...")
    
    # Check if defense already exists
    existing = defenses_collection.find_one({"defense_id": defense["defense_id"]})
    if existing:
        print(f"  ⚠️  Defense '{defense['name']}' already exists, updating...")
        # Update existing defense
        defenses_collection.update_one(
            {"defense_id": defense["defense_id"]},
            {"$set": {
                "name": defense["name"],
                "description": defense["description"],
                "zone_definitions": defense["zone_definitions"],
                "shift_triggers": defense["shift_triggers"]
            }}
        )
        print(f"  ✅ Updated: {defense['name']} (defense_id: {defense['defense_id']})")
    else:
        result = defenses_collection.insert_one(defense)
        print(f"  ✅ Inserted: {defense['name']} (defense_id: {defense['defense_id']})")
    
    # Verify
    added_defense = defenses_collection.find_one({"defense_id": defense["defense_id"]})
    if added_defense:
        print(f"\n✅ Verification - Found defense:")
        print(f"  {added_defense['defense_id']}: {added_defense['name']} ({added_defense['defense_type']})")
        print(f"  Effectiveness: {added_defense.get('effectiveness', 0.0)}")
        print(f"  Shift triggers: {added_defense.get('shift_triggers', {})}")
    else:
        print("\n❌ Error: Defense not found after insertion!")

if __name__ == "__main__":
    add_32_zone_defense()

