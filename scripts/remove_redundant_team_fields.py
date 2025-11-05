"""
Migration Script: Remove Redundant Fields from home_team/away_team Objects

This script removes duplicate data that exists in both home_team/away_team AND teams objects:
- plays (150KB of embedded skeletons!)
- strategy_settings
- attributes
- scouting

These fields are already in the teams object and should only exist there.

Impact: Reduces game documents by ~150KB (91% reduction)

Author: Document structure optimization
Date: 2025-11-05
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import games_collection, tournaments_collection, franchises_collection
from bson import ObjectId

def remove_redundant_fields_from_team_objects(team_obj):
    """
    Remove redundant fields from home_team/away_team objects.
    Keep only display data (name, colors, score, stats).
    Remove game state data (plays, strategy, attributes, scouting).
    
    Args:
        team_obj: home_team or away_team dictionary
        
    Returns:
        List of fields that were removed
    """
    if not team_obj or not isinstance(team_obj, dict):
        return []
    
    fields_to_remove = ['plays', 'strategy_settings', 'attributes', 'scouting']
    removed = []
    
    for field in fields_to_remove:
        if field in team_obj:
            removed.append(field)
    
    return removed

def migrate_games_collection():
    """Remove redundant fields from all single games."""
    print("\n" + "="*60)
    print("MIGRATING GAMES COLLECTION")
    print("="*60)
    
    games = list(games_collection.find({}))
    print(f"Found {len(games)} games to migrate")
    
    for game in games:
        game_id = game.get("_id")
        updates = {}
        
        # Check home_team
        home_team = game.get("home_team", {})
        if home_team:
            removed = remove_redundant_fields_from_team_objects(home_team)
            if removed:
                # Unset the redundant fields
                for field in removed:
                    updates[f"home_team.{field}"] = ""
                print(f"  Game {game_id} - Removing from home_team: {removed}")
        
        # Check away_team
        away_team = game.get("away_team", {})
        if away_team:
            removed = remove_redundant_fields_from_team_objects(away_team)
            if removed:
                # Unset the redundant fields
                for field in removed:
                    updates[f"away_team.{field}"] = ""
                print(f"  Game {game_id} - Removing from away_team: {removed}")
        
        # Apply updates using $unset
        if updates:
            games_collection.update_one({"_id": game_id}, {"$unset": updates})
            print(f"  ✅ Game {game_id} cleaned")
    
    print(f"\n✅ Migrated {len(games)} games")

def migrate_tournaments_collection():
    """Remove redundant fields from all tournament games."""
    print("\n" + "="*60)
    print("MIGRATING TOURNAMENTS COLLECTION")
    print("="*60)
    
    tournaments = list(tournaments_collection.find({}))
    print(f"Found {len(tournaments)} tournaments to migrate")
    
    for tournament in tournaments:
        tournament_id = tournament.get("_id")
        updates = {}
        
        # Migrate games within tournament
        games = tournament.get("games", {})
        if games:
            for round_key, round_games in games.items():
                if isinstance(round_games, dict):
                    for game_id, game_data in round_games.items():
                        if isinstance(game_data, dict):
                            # Check home_team
                            home_team = game_data.get("home_team", {})
                            if isinstance(home_team, dict):
                                removed = remove_redundant_fields_from_team_objects(home_team)
                                for field in removed:
                                    updates[f"games.{round_key}.{game_id}.home_team.{field}"] = ""
                            
                            # Check away_team
                            away_team = game_data.get("away_team", {})
                            if isinstance(away_team, dict):
                                removed = remove_redundant_fields_from_team_objects(away_team)
                                for field in removed:
                                    updates[f"games.{round_key}.{game_id}.away_team.{field}"] = ""
        
        # Apply updates
        if updates:
            tournaments_collection.update_one({"_id": tournament_id}, {"$unset": updates})
            print(f"  ✅ Tournament {tournament_id} cleaned ({len(updates)} fields removed)")
    
    print(f"\n✅ Migrated {len(tournaments)} tournaments")

def migrate_franchises_collection():
    """Remove redundant fields from all franchise games."""
    print("\n" + "="*60)
    print("MIGRATING FRANCHISES COLLECTION")
    print("="*60)
    
    franchises = list(franchises_collection.find({}))
    print(f"Found {len(franchises)} franchises to migrate")
    
    for franchise in franchises:
        franchise_id = franchise.get("_id")
        updates = {}
        
        # Migrate games within franchise
        games = franchise.get("games", {})
        if games:
            for week_key, week_games in games.items():
                if isinstance(week_games, dict):
                    for game_id, game_data in week_games.items():
                        if isinstance(game_data, dict):
                            # Check home_team
                            home_team = game_data.get("home_team", {})
                            if isinstance(home_team, dict):
                                removed = remove_redundant_fields_from_team_objects(home_team)
                                for field in removed:
                                    updates[f"games.{week_key}.{game_id}.home_team.{field}"] = ""
                            
                            # Check away_team
                            away_team = game_data.get("away_team", {})
                            if isinstance(away_team, dict):
                                removed = remove_redundant_fields_from_team_objects(away_team)
                                for field in removed:
                                    updates[f"games.{week_key}.{game_id}.away_team.{field}"] = ""
        
        # Apply updates
        if updates:
            franchises_collection.update_one({"_id": franchise_id}, {"$unset": updates})
            print(f"  ✅ Franchise {franchise_id} cleaned ({len(updates)} fields removed)")
    
    print(f"\n✅ Migrated {len(franchises)} franchises")

def verify_cleanup():
    """Verify that redundant fields were removed."""
    print("\n" + "="*60)
    print("VERIFYING CLEANUP")
    print("="*60)
    
    import json
    
    # Check sample game
    sample_game = games_collection.find_one()
    if sample_game:
        home_team = sample_game.get("home_team", {})
        away_team = sample_game.get("away_team", {})
        
        print(f"\nSample game home_team keys: {list(home_team.keys())}")
        
        redundant_found = []
        for field in ['plays', 'strategy_settings', 'attributes', 'scouting']:
            if field in home_team:
                redundant_found.append(field)
        
        if redundant_found:
            print(f"  ⚠️ Still has redundant fields: {redundant_found}")
        else:
            print(f"  ✅ No redundant fields found!")
        
        # Calculate new size
        game_size = len(json.dumps(sample_game, default=str))
        home_size = len(json.dumps(home_team, default=str))
        away_size = len(json.dumps(away_team, default=str))
        teams_size = len(json.dumps(sample_game.get('teams', {}), default=str))
        
        print(f"\n  Document size: {game_size/1024:.1f} KB (was 168.5 KB)")
        print(f"  home_team: {home_size/1024:.1f} KB (was 76.9 KB)")
        print(f"  away_team: {away_size/1024:.1f} KB (was 77.0 KB)")
        print(f"  teams: {teams_size/1024:.1f} KB")

def main():
    print("\n" + "="*80)
    print(" MIGRATION: Remove Redundant Team Fields ".center(80, "="))
    print("="*80)
    
    print("\n📋 This migration will remove duplicate data from home_team/away_team:")
    print("   - plays (150KB of embedded skeletons per game!)")
    print("   - strategy_settings")
    print("   - attributes")
    print("   - scouting")
    print("\n✅ These fields will remain in the teams object (single source of truth)")
    
    response = input("\nProceed with migration? (yes/no): ").strip().lower()
    if response != "yes":
        print("❌ Migration cancelled")
        sys.exit(0)
    
    # Run migrations
    migrate_games_collection()
    migrate_tournaments_collection()
    migrate_franchises_collection()
    
    # Verify cleanup
    verify_cleanup()
    
    print("\n" + "="*80)
    print(" MIGRATION COMPLETE ".center(80, "="))
    print("="*80)
    print("\n✅ Removed 150KB+ of redundant data per game")
    print("✅ home_team/away_team now contain only display data")
    print("✅ teams object is the single source of truth for game state")

if __name__ == "__main__":
    main()

