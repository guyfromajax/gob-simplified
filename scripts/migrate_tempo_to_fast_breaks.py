"""
Migration script to update all team documents in the universal teams collection.
Changes 'tempo' field to 'fast_breaks' in strategy_settings.

This script:
1. Finds all teams in the teams collection
2. Updates strategy_settings.tempo to strategy_settings.fast_breaks
3. Preserves the existing tempo value as fast_breaks value
"""

import sys
import os

# Add parent directory to path to import BackEnd modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import teams_collection

def migrate_teams():
    """Update all team documents: tempo -> fast_breaks in strategy_settings."""
    
    teams = list(teams_collection.find({}))
    print(f"Found {len(teams)} teams to update")
    
    updated_count = 0
    for team in teams:
        team_name = team.get("name", "Unknown")
        team_id = team.get("_id")
        
        # Check if strategy_settings exists and has tempo
        strategy_settings = team.get("strategy_settings", {})
        if "tempo" in strategy_settings:
            tempo_value = strategy_settings["tempo"]
            
            # Update: rename tempo to fast_breaks
            update_result = teams_collection.update_one(
                {"_id": team_id},
                {
                    "$set": {
                        "strategy_settings.fast_breaks": tempo_value
                    },
                    "$unset": {
                        "strategy_settings.tempo": ""
                    }
                }
            )
            
            if update_result.modified_count > 0:
                updated_count += 1
                print(f"✅ Updated {team_name}: tempo={tempo_value} -> fast_breaks={tempo_value}")
            else:
                print(f"⚠️  No update needed for {team_name} (may have already been migrated)")
        else:
            print(f"⚠️  {team_name} has no 'tempo' field in strategy_settings (may already be migrated or missing)")
    
    print(f"\n✅ Migration complete: {updated_count} teams updated")
    return updated_count

if __name__ == "__main__":
    print("🔄 Starting migration: tempo -> fast_breaks")
    print("=" * 50)
    migrate_teams()
    print("=" * 50)
    print("✅ Migration finished")

