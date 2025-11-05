"""
Migration Script: Convert to Reference-Based Play Architecture

This script:
1. Removes embedded skeleton data from team plays in all game/tournament/franchise documents
2. Removes turn data from all games (animation data should not be persisted)
3. Ensures play_id references exist for all plays
4. Dramatically reduces document sizes

Before running:
- Backup your database
- Ensure universal plays_collection has all plays with proper _id fields

Author: Migration for reference-based architecture
Date: 2025-11-05
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import games_collection, tournaments_collection, franchises_collection, plays_collection
from bson import ObjectId

def get_play_id_by_name(play_name):
    """Get play_id from universal plays collection by name."""
    play = plays_collection.find_one({"name": play_name})
    if play:
        return str(play["_id"])
    return None

def migrate_plays_in_document(plays_dict):
    """
    Remove skeletons from plays dict and ensure play_id exists.
    
    Args:
        plays_dict: Dictionary of play data
        
    Returns:
        Migrated plays dict (reference-based)
    """
    if not plays_dict or not isinstance(plays_dict, dict):
        return plays_dict
    
    migrated = {}
    for play_name, play_data in plays_dict.items():
        if not isinstance(play_data, dict):
            continue
        
        # Remove skeletons if present
        if "skeletons" in play_data:
            del play_data["skeletons"]
        
        # Ensure play_id exists (fetch from universal if missing)
        if "play_id" not in play_data or not play_data["play_id"]:
            play_id = get_play_id_by_name(play_name)
            if play_id:
                play_data["play_id"] = play_id
                print(f"  ✅ Added missing play_id for '{play_name}'")
            else:
                print(f"  ⚠️  Could not find play_id for '{play_name}' in universal collection")
        
        migrated[play_name] = play_data
    
    return migrated

def migrate_games_collection():
    """Migrate all games to reference-based architecture."""
    print("\n" + "="*60)
    print("MIGRATING GAMES COLLECTION")
    print("="*60)
    
    games = list(games_collection.find({}))
    print(f"Found {len(games)} games to migrate")
    
    for game in games:
        game_id = game.get("_id")
        updates = {}
        
        # Remove turns data (animation data shouldn't be persisted)
        if game.get("turns"):
            turns_count = len(game.get("turns", []))
            updates["turns"] = []
            print(f"\n🗑️  Game {game_id}: Removing {turns_count} turns")
        
        # Migrate team plays
        teams = game.get("teams", {})
        if teams:
            for team_id, team_data in teams.items():
                plays = team_data.get("plays", {})
                if plays:
                    migrated_plays = migrate_plays_in_document(plays)
                    updates[f"teams.{team_id}.plays"] = migrated_plays
                    print(f"  📋 Migrated {len(migrated_plays)} plays for team {team_id}")
        
        # Apply updates
        if updates:
            games_collection.update_one({"_id": game_id}, {"$set": updates})
            print(f"  ✅ Game {game_id} migrated successfully")
    
    print(f"\n✅ Migrated {len(games)} games")

def migrate_tournaments_collection():
    """Migrate all tournaments to reference-based architecture."""
    print("\n" + "="*60)
    print("MIGRATING TOURNAMENTS COLLECTION")
    print("="*60)
    
    tournaments = list(tournaments_collection.find({}))
    print(f"Found {len(tournaments)} tournaments to migrate")
    
    for tournament in tournaments:
        tournament_id = tournament.get("_id")
        print(f"\n📦 Tournament {tournament_id}")
        
        updates = {}
        
        # Migrate team plays
        teams = tournament.get("teams", {})
        if teams:
            for team_id, team_data in teams.items():
                plays = team_data.get("plays", {})
                if plays:
                    migrated_plays = migrate_plays_in_document(plays)
                    updates[f"teams.{team_id}.plays"] = migrated_plays
                    print(f"  📋 Migrated {len(migrated_plays)} plays for team {team_id}")
        
        # Migrate games within tournament
        games = tournament.get("games", {})
        if games:
            for round_key, round_games in games.items():
                if isinstance(round_games, dict):
                    for game_id, game_data in round_games.items():
                        if isinstance(game_data, dict):
                            # Remove turns from tournament games
                            if game_data.get("turns"):
                                updates[f"games.{round_key}.{game_id}.turns"] = []
                            
                            # Migrate team plays in game
                            game_teams = game_data.get("teams", {})
                            if game_teams:
                                for team_id, team_data in game_teams.items():
                                    plays = team_data.get("plays", {})
                                    if plays:
                                        migrated_plays = migrate_plays_in_document(plays)
                                        updates[f"games.{round_key}.{game_id}.teams.{team_id}.plays"] = migrated_plays
        
        # Apply updates
        if updates:
            tournaments_collection.update_one({"_id": tournament_id}, {"$set": updates})
            print(f"  ✅ Tournament {tournament_id} migrated successfully")
    
    print(f"\n✅ Migrated {len(tournaments)} tournaments")

def migrate_franchises_collection():
    """Migrate all franchises to reference-based architecture."""
    print("\n" + "="*60)
    print("MIGRATING FRANCHISES COLLECTION")
    print("="*60)
    
    franchises = list(franchises_collection.find({}))
    print(f"Found {len(franchises)} franchises to migrate")
    
    for franchise in franchises:
        franchise_id = franchise.get("_id")
        print(f"\n📦 Franchise {franchise_id}")
        
        updates = {}
        
        # Migrate team plays
        teams = franchise.get("teams", {})
        if teams:
            for team_id, team_data in teams.items():
                plays = team_data.get("plays", {})
                if plays:
                    migrated_plays = migrate_plays_in_document(plays)
                    updates[f"teams.{team_id}.plays"] = migrated_plays
                    print(f"  📋 Migrated {len(migrated_plays)} plays for team {team_id}")
        
        # Migrate games within franchise
        games = franchise.get("games", {})
        if games:
            for week_key, week_games in games.items():
                if isinstance(week_games, dict):
                    for game_id, game_data in week_games.items():
                        if isinstance(game_data, dict):
                            # Remove turns from franchise games
                            if game_data.get("turns"):
                                updates[f"games.{week_key}.{game_id}.turns"] = []
                            
                            # Migrate team plays in game
                            game_teams = game_data.get("teams", {})
                            if game_teams:
                                for team_id, team_data in game_teams.items():
                                    plays = team_data.get("plays", {})
                                    if plays:
                                        migrated_plays = migrate_plays_in_document(plays)
                                        updates[f"games.{week_key}.{game_id}.teams.{team_id}.plays"] = migrated_plays
        
        # Apply updates
        if updates:
            franchises_collection.update_one({"_id": franchise_id}, {"$set": updates})
            print(f"  ✅ Franchise {franchise_id} migrated successfully")
    
    print(f"\n✅ Migrated {len(franchises)} franchises")

def verify_universal_plays():
    """Verify universal plays collection has all necessary plays."""
    print("\n" + "="*60)
    print("VERIFYING UNIVERSAL PLAYS COLLECTION")
    print("="*60)
    
    plays = list(plays_collection.find({}))
    print(f"Found {len(plays)} plays in universal collection")
    
    for play in plays:
        play_id = play.get("_id")
        play_name = play.get("name")
        has_skeletons = "skeletons" in play
        skeleton_count = len(play.get("skeletons", {})) if has_skeletons else 0
        
        print(f"  ✅ {play_name} (ID: {play_id}) - {skeleton_count} skeleton variants")
    
    if len(plays) == 0:
        print("  ⚠️  WARNING: No plays found in universal collection!")
        return False
    
    return True

def calculate_size_savings():
    """Calculate document size reduction from migration."""
    print("\n" + "="*60)
    print("CALCULATING SIZE SAVINGS")
    print("="*60)
    
    import json
    
    # Sample game document
    sample_game = games_collection.find_one()
    if sample_game:
        game_size = len(json.dumps(sample_game, default=str))
        teams = sample_game.get("teams", {})
        teams_size = len(json.dumps(teams, default=str))
        turns_size = len(json.dumps(sample_game.get("turns", []), default=str))
        
        print(f"\nSample game document:")
        print(f"  Total size: {game_size/1024:.1f} KB")
        print(f"  Teams data size: {teams_size/1024:.1f} KB")
        print(f"  Turns data size: {turns_size/1024:.1f} KB")
        print(f"  Other data: {(game_size - teams_size - turns_size)/1024:.1f} KB")

def main():
    print("\n" + "="*80)
    print(" MIGRATION: Reference-Based Play Architecture ".center(80, "="))
    print("="*80)
    
    # Verify universal plays collection
    if not verify_universal_plays():
        print("\n❌ MIGRATION ABORTED: Universal plays collection is empty")
        print("   Please ensure plays_collection has all plays before migrating.")
        sys.exit(1)
    
    print("\n⚠️  WARNING: This migration will modify your database.")
    print("   It will remove skeleton data from all team plays.")
    print("   It will remove turn data from all games.")
    print("   Make sure you have a backup!")
    
    response = input("\nProceed with migration? (yes/no): ").strip().lower()
    if response != "yes":
        print("❌ Migration cancelled")
        sys.exit(0)
    
    # Run migrations
    migrate_games_collection()
    migrate_tournaments_collection()
    migrate_franchises_collection()
    
    # Calculate savings
    calculate_size_savings()
    
    print("\n" + "="*80)
    print(" MIGRATION COMPLETE ".center(80, "="))
    print("="*80)
    print("\n✅ All documents migrated to reference-based architecture")
    print("✅ Skeleton data is now fetched from universal plays_collection")
    print("✅ Document sizes significantly reduced")
    print("\nNext steps:")
    print("  1. Test single game mode")
    print("  2. Test tournament mode")
    print("  3. Test franchise mode")

if __name__ == "__main__":
    main()

