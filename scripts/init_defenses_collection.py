"""
Initialize defenses_collection in MongoDB with Man and 2-3 Zone entries.

This creates the base defensive playcall definitions with:
- defense_id, defense_type, name, description
- effectiveness (top-level field)
- game_stats, season_stats (usage and success tracking)
- zone_definitions (for zone types only, None for Man)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import defenses_collection

def init_defenses_collection():
    """Initialize defenses_collection with Man and 2-3 Zone entries."""
    
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
    
    defenses = [
        {
            "defense_id": "man",
            "defense_type": "Man",
            "name": "Man-to-Man",
            "description": "Standard man-to-man defense where each defender guards a specific offensive player",
            "effectiveness": 0.0,  # Top-level field (not in stats)
            "game_stats": create_granular_stats(),
            "season_stats": create_granular_stats(),
            "zone_definitions": None,  # Man defense doesn't use zones
            "shift_triggers": None  # Man defense doesn't use shifts
        },
        {
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
    ]
    
    print("Initializing defenses_collection...")
    
    # Clear existing entries (optional - remove if you want to preserve existing data)
    # defenses_collection.delete_many({})
    
    # Insert defenses
    inserted_count = 0
    for defense in defenses:
        # Check if defense already exists
        existing = defenses_collection.find_one({"defense_id": defense["defense_id"]})
        if existing:
            print(f"  ⚠️  Defense '{defense['name']}' already exists, skipping...")
            continue
        
        result = defenses_collection.insert_one(defense)
        inserted_count += 1
        print(f"  ✅ Inserted: {defense['name']} (defense_id: {defense['defense_id']})")
    
    print(f"\n✅ Initialization complete: {inserted_count} defense(s) inserted")
    
    # Verify
    all_defenses = list(defenses_collection.find({}, {"defense_id": 1, "name": 1, "defense_type": 1, "effectiveness": 1}))
    print(f"\nVerification - Found {len(all_defenses)} defense(s):")
    for defense in all_defenses:
        print(f"  {defense['defense_id']}: {defense['name']} ({defense['defense_type']}) - effectiveness: {defense.get('effectiveness', 0.0)}")

if __name__ == "__main__":
    init_defenses_collection()

