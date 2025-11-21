"""
Add 1-3-1 Zone Defense to the defenses_collection in MongoDB.

This script adds the 1-3-1 zone defense definition with:
- defense_id, defense_type, name, description
- effectiveness (top-level field)
- game_stats, season_stats (usage and success tracking)
- zone_definitions (normal, lower_shift, lower_corner_shift, upper_shift, upper_corner_shift)
- shift_triggers (which spots trigger shifts)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import defenses_collection

def add_131_zone_defense():
    """Add 1-3-1 Zone Defense to defenses_collection."""
    
    # Import zone definitions from shared_defense
    from BackEnd.utils.shared_defense import (
        ZONE_131_NORMAL,
        ZONE_131_LOWER_SHIFT,
        ZONE_131_LOWER_CORNER_SHIFT,
        ZONE_131_UPPER_SHIFT,
        ZONE_131_UPPER_CORNER_SHIFT
    )
    
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
        "defense_id": "1-3-1-zone",
        "defense_type": "Zone",
        "name": "1-3-1 Zone",
        "description": "1-3-1 zone defense with one guard up top, three players in the middle, and one player in the paint",
        "effectiveness": 0.0,  # Top-level field (not in stats)
        "game_stats": create_granular_stats(),
        "season_stats": create_granular_stats(),
        "zone_definitions": {
            "normal": ZONE_131_NORMAL,
            "lower_shift": ZONE_131_LOWER_SHIFT,
            "lower_corner_shift": ZONE_131_LOWER_CORNER_SHIFT,
            "upper_shift": ZONE_131_UPPER_SHIFT,
            "upper_corner_shift": ZONE_131_UPPER_CORNER_SHIFT
        },
        "shift_triggers": {
            "lower_shift": ["lower wing", "lower midWing", "lower midCorner"],
            "lower_corner_shift": ["lower corner"],
            "upper_shift": ["upper wing", "upper midWing", "upper midCorner"],
            "upper_corner_shift": ["upper corner"]
        }
    }
    
    print("Adding 1-3-1 Zone Defense to defenses_collection...")
    
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
    add_131_zone_defense()

