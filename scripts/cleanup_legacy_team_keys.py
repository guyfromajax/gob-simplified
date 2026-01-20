#!/usr/bin/env python3
"""
Cleanup script to remove legacy team name keys from game documents.

This script removes team entries that use team names as keys (e.g., "Ocean City")
instead of team_id keys (e.g., "OCEAN_CITY") from game documents.

Only removes entries if:
1. The entry uses a team name as the key (not uppercase with underscores)
2. A corresponding team_id key exists in the same document
3. The team_id key has playbook_settings (indicating it's the correct entry)
"""

import sys
import os
from pathlib import Path

# Add BackEnd to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from BackEnd.db import games_collection
from bson import ObjectId
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_team_id_key(key: str) -> bool:
    """Check if a key looks like a team_id (uppercase with underscores)."""
    return key.isupper() and "_" in key

def is_team_name_key(key: str) -> bool:
    """Check if a key looks like a team name (not team_id format)."""
    return not is_team_id_key(key) and key and not key.startswith("_")

def cleanup_legacy_team_keys(dry_run: bool = True):
    """
    Remove legacy team name keys from game documents.
    
    Args:
        dry_run: If True, only log what would be removed without making changes
    """
    logger.info(f"🔍 Starting cleanup (dry_run={dry_run})...")
    
    games = list(games_collection.find({}))
    logger.info(f"📊 Found {len(games)} game documents to check")
    
    total_removed = 0
    total_checked = 0
    
    for game in games:
        game_id = game.get("_id")
        teams = game.get("teams", {})
        
        if not teams:
            continue
        
        total_checked += 1
        legacy_keys_to_remove = []
        
        # Find all team name keys (not team_id format)
        for key in teams.keys():
            if is_team_name_key(key):
                team_data = teams.get(key, {})
                
                # Check if there's a corresponding team_id key
                # Try to find team_id by matching team name
                team_name = team_data.get("name", key)
                corresponding_team_id = None
                
                for tid_key in teams.keys():
                    if is_team_id_key(tid_key):
                        tid_data = teams.get(tid_key, {})
                        if tid_data.get("name") == team_name:
                            corresponding_team_id = tid_key
                            break
                
                # Only remove if:
                # 1. We found a corresponding team_id key
                # 2. The team_id key has playbook_settings (indicating it's the correct entry)
                if corresponding_team_id:
                    tid_data = teams.get(corresponding_team_id, {})
                    if tid_data.get("playbook_settings"):
                        legacy_keys_to_remove.append(key)
                        logger.info(f"  ✅ Found legacy key '{key}' in game {game_id} (corresponds to '{corresponding_team_id}')")
        
        if legacy_keys_to_remove:
            logger.info(f"📝 Game {game_id}: Would remove {len(legacy_keys_to_remove)} legacy keys: {legacy_keys_to_remove}")
            
            if not dry_run:
                # Build unset operation to remove legacy keys
                unset_dict = {}
                for key in legacy_keys_to_remove:
                    unset_dict[f"teams.{key}"] = ""
                
                result = games_collection.update_one(
                    {"_id": game_id},
                    {"$unset": unset_dict}
                )
                
                if result.modified_count > 0:
                    logger.info(f"  ✅ Removed {len(legacy_keys_to_remove)} legacy keys from game {game_id}")
                    total_removed += len(legacy_keys_to_remove)
                else:
                    logger.warning(f"  ⚠️ Failed to remove legacy keys from game {game_id}")
    
    logger.info(f"📊 Summary: Checked {total_checked} games, {'Would remove' if dry_run else 'Removed'} {total_removed} legacy team keys")
    
    if dry_run:
        logger.info("🔍 This was a dry run. Run with --execute to actually remove the keys.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup legacy team name keys from game documents")
    parser.add_argument("--execute", action="store_true", help="Actually remove the keys (default is dry run)")
    
    args = parser.parse_args()
    
    cleanup_legacy_team_keys(dry_run=not args.execute)

