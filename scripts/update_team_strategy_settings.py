"""
Migration script to add new strategy_settings fields to all team documents in MongoDB.

Adds 11 strategy categories (0-4 scale):
- offense, inside, attack, outside
- tempo, play_calling
- defense, aggression
- hc_trap, fc_press
- rebounding

Default value: 2 (neutral/balanced)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import get_db

def update_team_strategy_settings():
    """Add new strategy_settings fields to all team documents."""
    db = get_db()
    
    new_fields = {
        "strategy_settings.offense": 2,
        "strategy_settings.inside": 2,
        "strategy_settings.attack": 2,
        "strategy_settings.outside": 2,
        "strategy_settings.tempo": 2,
        "strategy_settings.play_calling": 2,
        "strategy_settings.defense": 2,
        "strategy_settings.aggression": 2,
        "strategy_settings.hc_trap": 2,
        "strategy_settings.fc_press": 2,
        "strategy_settings.rebounding": 2
    }
    
    print("Updating team documents with new strategy_settings...")
    
    # Update all team documents
    result = db.teams.update_many(
        {},  # All teams
        {"$set": new_fields}
    )
    
    print(f"✓ Updated {result.modified_count} team documents")
    
    # Verify
    teams = list(db.teams.find({}, {"name": 1, "strategy_settings": 1}))
    print(f"\nVerification - Found {len(teams)} teams:")
    for team in teams:
        settings = team.get("strategy_settings", {})
        print(f"  {team['name']}: {len(settings)} strategy fields")
        if len(settings) < 11:
            print(f"    ⚠️  Missing fields: {11 - len(settings)}")
    
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    update_team_strategy_settings()

