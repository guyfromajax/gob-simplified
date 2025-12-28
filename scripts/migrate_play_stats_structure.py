"""
Migration Script: Update Play Stats Structure

This script migrates existing franchise and tournament instances to the new play stats structure:
- Removes: shot_attempts, made_shots, turnovers, offensive_fouls, defensive_fouls
- Adds: successes, player_points (dictionary)

Before:
{
  "game_stats": {
    "times_run": 5,
    "shot_attempts": 10,
    "made_shots": 6,
    "turnovers": 2,
    "offensive_fouls": 1,
    "defensive_fouls": 0,
    "effectiveness": 0.6
  },
  "season_stats": {
    "times_run": 20,
    "shot_attempts": 40,
    "made_shots": 24,
    "turnovers": 8,
    "offensive_fouls": 4,
    "defensive_fouls": 2,
    "effectiveness": 0.6
  }
}

After:
{
  "game_stats": {
    "times_run": 5,
    "successes": 0,  # Will be recalculated from existing data if possible
    "player_points": {},  # Empty initially, will be populated during gameplay
    "effectiveness": 0.6
  },
  "season_stats": {
    "times_run": 20,
    "successes": 0,  # Will be recalculated from existing data if possible
    "player_points": {},  # Empty initially, will be populated during gameplay
    "effectiveness": 0.6
  }
}

Note: This migration preserves times_run and effectiveness, but resets successes and player_points
since we cannot reliably calculate successes from the old structure (successes = makes + defensive fouls).

Author: Migration for new play stats tracking system
Date: 2025-01-XX
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import franchises_collection, tournaments_collection
from bson import ObjectId


def migrate_plays_in_team(plays_dict, team_name):
    """
    Migrate plays structure for a single team.
    
    Args:
        plays_dict: Dictionary of plays for a team
        team_name: Name of the team (for logging)
        
    Returns:
        dict: Updated plays_dict with new structure, or None if no changes needed
    """
    if not plays_dict:
        return None
    
    updated_plays = {}
    changes_made = False
    
    for play_name, play_data in plays_dict.items():
        updated_play = play_data.copy()
        play_changed = False
        
        # Migrate game_stats
        if "game_stats" in play_data:
            old_game_stats = play_data["game_stats"]
            new_game_stats = {
                "times_run": old_game_stats.get("times_run", 0),
                "successes": 0,  # Reset - cannot reliably calculate from old structure
                "player_points": {},  # Empty - will be populated during gameplay
                "effectiveness": old_game_stats.get("effectiveness", 0.0)
            }
            updated_play["game_stats"] = new_game_stats
            play_changed = True
        
        # Migrate season_stats
        if "season_stats" in play_data:
            old_season_stats = play_data["season_stats"]
            new_season_stats = {
                "times_run": old_season_stats.get("times_run", 0),
                "successes": 0,  # Reset - cannot reliably calculate from old structure
                "player_points": {},  # Empty - will be populated during gameplay
                "effectiveness": old_season_stats.get("effectiveness", 0.0)
            }
            updated_play["season_stats"] = new_season_stats
            play_changed = True
        
        if play_changed:
            updated_plays[play_name] = updated_play
            changes_made = True
        else:
            updated_plays[play_name] = play_data
    
    return updated_plays if changes_made else None


def migrate_franchises_collection():
    """Migrate all franchise documents."""
    print("\n" + "="*80)
    print(" MIGRATING FRANCHISE DOCUMENTS ".center(80, "="))
    print("="*80)
    
    franchises = list(franchises_collection.find({}))
    print(f"\nFound {len(franchises)} franchise documents")
    
    total_updated = 0
    total_teams_updated = 0
    total_plays_updated = 0
    
    for franchise in franchises:
        franchise_id = franchise.get("_id")
        franchise_name = franchise.get("name", "Unnamed")
        franchise_teams = franchise.get("franchise_teams", {})
        
        if not franchise_teams:
            continue
        
        franchise_updated = False
        teams_updated = 0
        plays_updated = 0
        
        update_operations = {}
        
        for team_id, team_data in franchise_teams.items():
            plays = team_data.get("plays", {})
            
            if not plays:
                continue
            
            # Check if migration is needed
            needs_migration = False
            for play_name, play_data in plays.items():
                game_stats = play_data.get("game_stats", {})
                season_stats = play_data.get("season_stats", {})
                
                # Check if old structure exists
                if "shot_attempts" in game_stats or "shot_attempts" in season_stats:
                    needs_migration = True
                    break
                # Check if new structure is missing
                if "successes" not in game_stats or "player_points" not in game_stats:
                    needs_migration = True
                    break
                if "season_stats" in play_data and ("successes" not in season_stats or "player_points" not in season_stats):
                    needs_migration = True
                    break
            
            if needs_migration:
                migrated_plays = migrate_plays_in_team(plays, team_id)
                if migrated_plays:
                    update_operations[f"franchise_teams.{team_id}.plays"] = migrated_plays
                    teams_updated += 1
                    plays_updated += len(migrated_plays)
                    franchise_updated = True
        
        if franchise_updated:
            # Update franchise document
            franchises_collection.update_one(
                {"_id": franchise_id},
                {"$set": update_operations}
            )
            total_updated += 1
            total_teams_updated += teams_updated
            total_plays_updated += plays_updated
            print(f"  ✅ {franchise_name}: Updated {teams_updated} teams, {plays_updated} plays")
        else:
            print(f"  ⏭️  {franchise_name}: Already migrated or no plays found")
    
    print(f"\n✅ Franchise migration complete:")
    print(f"   - {total_updated} franchises updated")
    print(f"   - {total_teams_updated} teams updated")
    print(f"   - {total_plays_updated} plays updated")


def migrate_tournaments_collection():
    """Migrate all tournament documents."""
    print("\n" + "="*80)
    print(" MIGRATING TOURNAMENT DOCUMENTS ".center(80, "="))
    print("="*80)
    
    tournaments = list(tournaments_collection.find({}))
    print(f"\nFound {len(tournaments)} tournament documents")
    
    total_updated = 0
    total_teams_updated = 0
    total_plays_updated = 0
    
    for tournament in tournaments:
        tournament_id = tournament.get("_id")
        tournament_name = tournament.get("name", "Unnamed")
        teams = tournament.get("teams", {})
        
        if not teams:
            continue
        
        tournament_updated = False
        teams_updated = 0
        plays_updated = 0
        
        update_operations = {}
        
        for team_id, team_data in teams.items():
            plays = team_data.get("plays", {})
            
            if not plays:
                continue
            
            # Check if migration is needed
            needs_migration = False
            for play_name, play_data in plays.items():
                game_stats = play_data.get("game_stats", {})
                season_stats = play_data.get("season_stats", {})
                
                # Check if old structure exists
                if "shot_attempts" in game_stats or "shot_attempts" in season_stats:
                    needs_migration = True
                    break
                # Check if new structure is missing
                if "successes" not in game_stats or "player_points" not in game_stats:
                    needs_migration = True
                    break
                if "season_stats" in play_data and ("successes" not in season_stats or "player_points" not in season_stats):
                    needs_migration = True
                    break
            
            if needs_migration:
                migrated_plays = migrate_plays_in_team(plays, team_id)
                if migrated_plays:
                    update_operations[f"teams.{team_id}.plays"] = migrated_plays
                    teams_updated += 1
                    plays_updated += len(migrated_plays)
                    tournament_updated = True
        
        if tournament_updated:
            # Update tournament document
            tournaments_collection.update_one(
                {"_id": tournament_id},
                {"$set": update_operations}
            )
            total_updated += 1
            total_teams_updated += teams_updated
            total_plays_updated += plays_updated
            print(f"  ✅ {tournament_name}: Updated {teams_updated} teams, {plays_updated} plays")
        else:
            print(f"  ⏭️  {tournament_name}: Already migrated or no plays found")
    
    print(f"\n✅ Tournament migration complete:")
    print(f"   - {total_updated} tournaments updated")
    print(f"   - {total_teams_updated} teams updated")
    print(f"   - {total_plays_updated} plays updated")


def main():
    print("\n" + "="*80)
    print(" MIGRATION: Play Stats Structure Update ".center(80, "="))
    print("="*80)
    print("\nThis migration will:")
    print("  - Remove: shot_attempts, made_shots, turnovers, offensive_fouls, defensive_fouls")
    print("  - Add: successes, player_points (dictionary)")
    print("  - Preserve: times_run, effectiveness")
    print("\n⚠️  WARNING: This migration will modify your database.")
    print("   Make sure you have a backup!")
    
    response = input("\nProceed with migration? (yes/no): ").strip().lower()
    if response != "yes":
        print("❌ Migration cancelled")
        sys.exit(0)
    
    # Run migrations
    migrate_franchises_collection()
    migrate_tournaments_collection()
    
    print("\n" + "="*80)
    print(" MIGRATION COMPLETE ".center(80, "="))
    print("="*80)
    print("\n✅ All franchise and tournament documents migrated to new play stats structure")
    print("✅ New plays will use the new structure automatically")
    print("\nNote: successes and player_points are reset to 0/{} and will be populated")
    print("      during gameplay going forward.")


if __name__ == "__main__":
    main()

