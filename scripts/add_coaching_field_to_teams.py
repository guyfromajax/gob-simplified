"""
Add coaching field to all teams in the universal teams collection.

This script adds a coaching structure to all team documents in the teams collection:
- effectiveness: 0
- training_focus_list: []
- authoritarian: {score: 0, momentum: 0}
- systems coach: {score: 0, momentum: 0}
- player maximizer: {score: 0, momentum: 0}
- culture builder: {score: 0, momentum: 0}
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import teams_collection

def add_coaching_field_to_teams():
    """Add coaching field structure to all teams in teams collection."""
    
    print("=" * 60)
    print("Adding coaching field to teams collection")
    print("=" * 60)
    
    # Define the coaching structure
    coaching_structure = {
        "effectiveness": 0,
        "training_focus_list": [],
        "authoritarian": {
            "score": 0,
            "momentum": 0
        },
        "systems coach": {
            "score": 0,
            "momentum": 0
        },
        "player maximizer": {
            "score": 0,
            "momentum": 0
        },
        "culture builder": {
            "score": 0,
            "momentum": 0
        }
    }
    
    # Count total teams
    total_teams = teams_collection.count_documents({})
    print(f"\n📋 Total teams in collection: {total_teams}")
    
    # Count teams missing coaching field
    teams_missing_coaching = teams_collection.count_documents({"coaching": {"$exists": False}})
    print(f"📋 Teams missing 'coaching' field: {teams_missing_coaching}")
    
    if teams_missing_coaching > 0:
        # Add coaching field to teams that don't have it
        result = teams_collection.update_many(
            {"coaching": {"$exists": False}},
            {"$set": {"coaching": coaching_structure}}
        )
        print(f"  ✅ Added 'coaching' field to {result.modified_count} team(s)")
    else:
        print(f"  ✓ All teams already have 'coaching' field")
    
    # Verify teams have coaching field
    teams_with_coaching = teams_collection.count_documents({"coaching": {"$exists": True}})
    print(f"  📊 Verification: {teams_with_coaching}/{total_teams} teams have 'coaching' field")
    
    # Check if any teams need structure updates (missing sub-fields)
    teams_needing_update = 0
    all_teams = teams_collection.find({})
    
    for team in all_teams:
        coaching = team.get("coaching", {})
        needs_update = False
        
        # Check if all required fields exist
        if not isinstance(coaching, dict):
            needs_update = True
        else:
            required_fields = [
                "effectiveness",
                "training_focus_list",
                "authoritarian",
                "systems coach",
                "player maximizer",
                "culture builder"
            ]
            
            for field in required_fields:
                if field not in coaching:
                    needs_update = True
                    break
            
            # Check sub-structures
            if not needs_update:
                for archetype in ["authoritarian", "systems coach", "player maximizer", "culture builder"]:
                    archetype_data = coaching.get(archetype, {})
                    if not isinstance(archetype_data, dict) or "score" not in archetype_data or "momentum" not in archetype_data:
                        needs_update = True
                        break
        
        if needs_update:
            teams_needing_update += 1
            # Update with full structure
            teams_collection.update_one(
                {"_id": team["_id"]},
                {"$set": {"coaching": coaching_structure}}
            )
    
    if teams_needing_update > 0:
        print(f"  ✅ Updated structure for {teams_needing_update} team(s) with incomplete coaching field")
    
    # Final verification
    print("\n" + "=" * 60)
    print("✅ Update complete!")
    print("=" * 60)
    
    # Show sample team coaching structure
    print("\n📋 Sample team coaching structure:")
    sample_team = teams_collection.find_one({}, {"name": 1, "coaching": 1})
    if sample_team:
        print(f"  Team: {sample_team.get('name', 'N/A')}")
        coaching = sample_team.get("coaching", {})
        print(f"  Has coaching field: {coaching is not None and isinstance(coaching, dict)}")
        if coaching:
            print(f"  Effectiveness: {coaching.get('effectiveness', 'MISSING')}")
            print(f"  Training focus list: {coaching.get('training_focus_list', 'MISSING')}")
            print(f"  Authoritarian score: {coaching.get('authoritarian', {}).get('score', 'MISSING')}")
            print(f"  Authoritarian momentum: {coaching.get('authoritarian', {}).get('momentum', 'MISSING')}")
            print(f"  Systems Coach score: {coaching.get('systems coach', {}).get('score', 'MISSING')}")
            print(f"  Culture Builder score: {coaching.get('culture builder', {}).get('score', 'MISSING')}")

if __name__ == "__main__":
    add_coaching_field_to_teams()

