#!/usr/bin/env python3
"""
Migration script to convert legacy team name keys to canonical team_id keys in game documents.

This script:
1. Finds all game documents with legacy team name keys (e.g., "Ocean City")
2. Converts them to canonical team_id keys (e.g., "OCEAN_CITY")
3. Merges data if both legacy and canonical keys exist
4. Preserves all team data (playbook_settings, strategy_settings, plays, etc.)

Phase 5.2: Remove Legacy Compatibility
"""

import sys
from pathlib import Path

# Add BackEnd to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from BackEnd.db import games_collection
from bson import ObjectId
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def is_team_id_key(key: str) -> bool:
    """Check if a key looks like a canonical team_id (uppercase with underscores)."""
    return key.isupper() and "_" in key


def is_team_name_key(key: str) -> bool:
    """Check if a key looks like a team name (not team_id format)."""
    return not is_team_id_key(key) and key and not key.startswith("_")


def normalize_team_name_to_canonical(team_name: str, teams: dict, home_team_id: str = None, away_team_id: str = None) -> str:
    """
    Normalize team name to canonical team_id format.
    
    Uses the same logic as normalize_team_id_to_canonical() helper:
    1. Try direct key match (if already canonical)
    2. Try name match (iterate through teams)
    3. Try home/away fallback
    4. Fail loudly if not found
    """
    # Step 1: Try direct key match (if team_name is already a team_id key)
    if team_name in teams and (team_name.isupper() and "_" in team_name):
        return team_name
    
    # Step 2: Try name match (iterate through teams)
    for tid in teams.keys():
        team_obj = teams.get(tid, {})
        # Match if key equals team name OR team_obj.name equals team name (case-insensitive)
        if tid == team_name or (team_obj.get("name") or "").lower() == (team_name or "").lower():
            return tid
    
    # Step 3: Try home/away fallback
    if home_team_id and home_team_id in teams:
        home_team_obj = teams.get(home_team_id, {})
        if home_team_id == team_name or home_team_obj.get("name") == team_name:
            return home_team_id
    if away_team_id and away_team_id in teams:
        away_team_obj = teams.get(away_team_id, {})
        if away_team_id == team_name or away_team_obj.get("name") == team_name:
            return away_team_id
    
    # Step 4: If still not found, try to derive canonical format from team name
    # Convert "Ocean City" -> "OCEAN_CITY"
    canonical = team_name.upper().replace(" ", "_").replace("-", "_")
    if canonical in teams:
        return canonical
    
    # If we can't resolve, return None (will be handled by caller)
    return None


def merge_team_data(canonical_data: dict, legacy_data: dict) -> dict:
    """
    Merge legacy team data into canonical team data.
    
    Priority: canonical data takes precedence, but legacy data fills in missing fields.
    """
    merged = canonical_data.copy() if canonical_data else {}
    
    # Merge all fields from legacy data
    for key, value in legacy_data.items():
        if key not in merged or not merged[key]:
            # If canonical doesn't have this field, use legacy
            merged[key] = value
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            # If both are dicts, merge recursively
            merged[key] = {**merged[key], **value}
    
    return merged


def migrate_game_document(game: dict, dry_run: bool = True) -> dict:
    """
    Migrate a single game document.
    
    Returns:
        dict with migration results: {"migrated": int, "errors": list}
    """
    game_id = game.get("_id")
    teams = game.get("teams", {})
    home_team_id = game.get("home_team_id")
    away_team_id = game.get("away_team_id")
    
    if not teams:
        return {"migrated": 0, "errors": []}
    
    migrated_count = 0
    errors = []
    updates = {}  # MongoDB update operations
    
    # Find all legacy team name keys
    for legacy_key in list(teams.keys()):
        if not is_team_name_key(legacy_key):
            continue
        
        legacy_data = teams.get(legacy_key, {})
        if not legacy_data:
            continue
        
        # Normalize to canonical team_id
        canonical_key = normalize_team_name_to_canonical(
            legacy_key, teams, home_team_id, away_team_id
        )
        
        if not canonical_key:
            error_msg = f"Could not resolve legacy key '{legacy_key}' to canonical team_id in game {game_id}"
            logger.warning(f"  ⚠️ {error_msg}")
            errors.append(error_msg)
            continue
        
        # Get existing canonical data (if any)
        canonical_data = teams.get(canonical_key, {})
        
        # Merge data
        merged_data = merge_team_data(canonical_data, legacy_data)
        
        # Prepare update operations
        if canonical_key not in updates:
            updates[canonical_key] = merged_data
        else:
            # If we already have an update for this key, merge again
            updates[canonical_key] = merge_team_data(updates[canonical_key], merged_data)
        
        logger.info(f"  ✅ Migrating '{legacy_key}' → '{canonical_key}' in game {game_id}")
        migrated_count += 1
    
    # Apply updates if not dry run
    if updates and not dry_run:
        # Build MongoDB update operations
        set_operations = {}
        unset_operations = {}
        
        for canonical_key, merged_data in updates.items():
            set_operations[f"teams.{canonical_key}"] = merged_data
        
        # Remove legacy keys
        for legacy_key in list(teams.keys()):
            if is_team_name_key(legacy_key):
                unset_operations[f"teams.{legacy_key}"] = ""
        
        # Execute update
        update_doc = {}
        if set_operations:
            update_doc["$set"] = set_operations
        if unset_operations:
            update_doc["$unset"] = unset_operations
        
        if update_doc:
            result = games_collection.update_one(
                {"_id": game_id},
                update_doc
            )
            
            if result.modified_count > 0:
                logger.info(f"  ✅ Successfully migrated {migrated_count} team keys in game {game_id}")
            else:
                error_msg = f"Failed to update game {game_id}"
                logger.error(f"  ❌ {error_msg}")
                errors.append(error_msg)
    
    return {"migrated": migrated_count, "errors": errors}


def migrate_all_games(dry_run: bool = True):
    """
    Migrate all game documents.
    
    Args:
        dry_run: If True, only log what would be migrated without making changes
    """
    logger.info(f"🔍 Starting migration (dry_run={dry_run})...")
    
    games = list(games_collection.find({}))
    logger.info(f"📊 Found {len(games)} game documents to check")
    
    total_migrated = 0
    total_checked = 0
    total_errors = 0
    
    for game in games:
        game_id = game.get("_id")
        teams = game.get("teams", {})
        
        if not teams:
            continue
        
        total_checked += 1
        result = migrate_game_document(game, dry_run=dry_run)
        
        total_migrated += result["migrated"]
        total_errors += len(result["errors"])
    
    logger.info(f"📊 Summary:")
    logger.info(f"  - Checked: {total_checked} games")
    logger.info(f"  - {'Would migrate' if dry_run else 'Migrated'}: {total_migrated} team keys")
    logger.info(f"  - Errors: {total_errors}")
    
    if dry_run:
        logger.info("🔍 This was a dry run. Run with --execute to actually migrate the data.")
    else:
        logger.info("✅ Migration complete!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate legacy team name keys to canonical team_id keys in game documents"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually migrate the data (default is dry run)"
    )
    
    args = parser.parse_args()
    
    migrate_all_games(dry_run=not args.execute)

