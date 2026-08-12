#!/usr/bin/env python3
"""
Migration Script: Tournament player_stats → players

This script migrates existing tournament documents from using `player_stats` 
to `players` key, aligning with Franchise Mode structure.

Changes:
1. Renames `player_stats` → `players` in tournament documents
2. Wraps player metadata in `meta` object (if not already wrapped)
3. Ensures structure matches Franchise pattern

Backward Compatibility:
- Code includes backward compatibility checks to read from either key
- This migration is safe to run multiple times (idempotent)
"""

import sys
import os
import argparse
from pathlib import Path

# Add parent directory to path to import BackEnd modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from bson import ObjectId
from scripts.db_migration_cli import connect_migration_target

def migrate_tournament_documents(tournaments_collection, *, apply: bool):
    """Migrate all tournament documents from player_stats to players."""
    db = get_database()
    tournaments_collection = db.tournaments
    
    # Find all tournaments
    tournaments = list(tournaments_collection.find({}))
    total = len(tournaments)
    
    if total == 0:
        print("✅ No tournament documents found. Nothing to migrate.")
        return
    
    print(f"📊 Found {total} tournament document(s) to migrate")
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    
    for tournament in tournaments:
        tournament_id = tournament.get("_id")
        tournament_id_str = str(tournament_id)
        
        try:
            # Check if already migrated (has players key, no player_stats key)
            has_players = "players" in tournament
            has_player_stats = "player_stats" in tournament
            
            if has_players and not has_player_stats:
                print(f"⏭️  Tournament {tournament_id_str}: Already migrated (has players, no player_stats)")
                skipped_count += 1
                continue
            
            # Get player_stats data
            player_stats = tournament.get("player_stats", {})
            
            if not player_stats:
                print(f"⏭️  Tournament {tournament_id_str}: No player_stats found, skipping")
                skipped_count += 1
                continue
            
            # Migrate player_stats to players
            players = {}
            
            for pid, pdata in player_stats.items():
                # Check if already has meta wrapper
                if "meta" in pdata:
                    # Already has meta wrapper, just copy structure
                    players[pid] = {
                        "meta": pdata.get("meta", {}),
                        "season": pdata.get("season", {}),
                        "attributes": pdata.get("attributes", {}),
                        "position_ratings": pdata.get("position_ratings", {})
                    }
                else:
                    # Need to wrap metadata in meta object
                    meta = {
                        "first_name": pdata.get("first_name", ""),
                        "last_name": pdata.get("last_name", ""),
                        "team": pdata.get("team", ""),
                    }
                    # Add team_id if present
                    if "team_id" in pdata:
                        meta["team_id"] = str(pdata["team_id"])
                    
                    players[pid] = {
                        "meta": meta,
                        "season": pdata.get("season", {}),
                        "attributes": pdata.get("attributes", {}),
                        "position_ratings": pdata.get("position_ratings", {})
                    }
            
            # Update tournament document
            update_doc = {
                "$set": {"players": players},
                "$unset": {"player_stats": ""}  # Remove old key
            }
            
            if not apply:
                print(f"[dry-run] Tournament {tournament_id_str}: would migrate {len(players)} players")
                migrated_count += 1
                continue
            result = tournaments_collection.update_one({"_id": tournament_id}, update_doc)
            
            if result.modified_count > 0:
                print(f"✅ Tournament {tournament_id_str}: Migrated {len(players)} players")
                migrated_count += 1
            else:
                print(f"⚠️  Tournament {tournament_id_str}: Update had no effect")
                error_count += 1
                
        except Exception as e:
            print(f"❌ Tournament {tournament_id_str}: Error - {e}")
            error_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("📊 Migration Summary:")
    print(f"   Total tournaments: {total}")
    print(f"   ✅ Migrated: {migrated_count}")
    print(f"   ⏭️  Skipped: {skipped_count}")
    print(f"   ❌ Errors: {error_count}")
    print("="*60)
    
    if migrated_count > 0:
        print("\n✅ Migration complete! Tournament documents now use 'players' key.")
        print("   Code includes backward compatibility for old 'player_stats' key.")
    elif skipped_count == total:
        print("\n✅ All tournaments already migrated or have no player data.")
    else:
        print("\n⚠️  Migration completed with some issues. Review errors above.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", choices=("gob-staging", "gob"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=args.apply)
    print("🔄 Starting Tournament player_stats → players migration...")
    print("="*60)
    migrate_tournament_documents(connection.database["tournaments"], apply=args.apply)
