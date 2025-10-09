#!/usr/bin/env python3
"""
Master Player Migration Script
===============================
Loads player data from teams/*.json files into MongoDB and performs all necessary setup:
1. Migrate players from JSON files to players_collection
2. Add/update height and weight from JSON files
3. Calculate and store position ratings
4. Update teams_collection with player_ids references

Usage: python scripts/migrate_players.py
"""

import os
import sys
import json
from pathlib import Path
from uuid import uuid4

# Make BackEnd importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from BackEnd.db import players_collection, teams_collection
from BackEnd.models.player import Player
from BackEnd.utils.position_ratings import compute_position_ratings

TEAMS_DIR = Path(__file__).resolve().parent.parent / "teams"

if not TEAMS_DIR.exists():
    raise SystemExit(f"Teams folder not found: {TEAMS_DIR}")

print("=" * 80)
print("MASTER PLAYER MIGRATION SCRIPT")
print("=" * 80)

# ============================================================================
# STEP 1: Migrate Players from JSON to MongoDB
# ============================================================================
print("\n[STEP 1] Migrating players from JSON files to MongoDB...")
print("-" * 80)

player_docs = []
player_height_weight_map = {}  # Store height/weight for later updates

for filename in sorted(os.listdir(TEAMS_DIR)):
    if not filename.endswith(".json") or filename.startswith("."):
        continue

    path = os.path.join(TEAMS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        team_data = json.load(f)
    
    team_name = team_data.get("name", "Unknown Team")
    print(f"\nProcessing team: {team_name}")

    for raw_player in team_data.get("players", []):
        # Ensure attributes are nested properly
        if "attributes" not in raw_player:
            raw_player["attributes"] = {
                k: raw_player.get(k, 0) for k in [
                    "SC", "SH", "ID", "OD", "PS", "BH",
                    "RB", "ST", "AG", "FT", "ND", "IQ", "CH", "EM", "MO"
                ]
            }
        
        try:
            player_obj = Player(raw_player)
            uuid_str = str(uuid4())
            
            # Store height/weight for reference
            player_key = (team_name, player_obj.first_name, player_obj.last_name)
            player_height_weight_map[player_key] = {
                "height": raw_player.get("height"),
                "weight": raw_player.get("weight"),
                "uuid": uuid_str
            }
            
            player_doc = {
                "_id": uuid_str,
                "player_id": uuid_str,
                "first_name": player_obj.first_name,
                "last_name": player_obj.last_name,
                "team": player_obj.team,
                "attributes": player_obj.attributes,
                "stats": player_obj.stats,
                "metadata": player_obj.metadata,
                "jersey": player_obj.jersey,
                "year": player_obj.year,
                "height": raw_player.get("height"),
                "weight": raw_player.get("weight")
            }
            player_docs.append(player_doc)
            print(f"  ✅ {player_obj.name} (#{player_obj.jersey})")
        except Exception as e:
            print(f"  ❌ Failed to load player: {e}")

# Clear and insert
print(f"\nClearing players collection and inserting {len(player_docs)} players...")
players_collection.delete_many({})
players_collection.insert_many(player_docs)
print(f"✅ Migrated {len(player_docs)} players into the players collection.")

# ============================================================================
# STEP 2: Calculate and Store Position Ratings
# ============================================================================
print("\n[STEP 2] Calculating position ratings for all players...")
print("-" * 80)

scanned = updated = 0

for doc in players_collection.find({}, {"team": 1, "first_name": 1, "last_name": 1, "attributes": 1, "height": 1}):
    scanned += 1
    ratings = compute_position_ratings(doc)
    
    res = players_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"position_ratings": ratings}}
    )
    
    name = f"{doc.get('first_name','?')} {doc.get('last_name','?')}"
    team = doc.get("team", "?")
    if res.modified_count:
        updated += 1
        print(f"SET: {team} — {name} -> {ratings}")
    else:
        print(f"OK:  {team} — {name} (no change)")

print(f"\n✅ Position ratings: {scanned} players scanned, {updated} updated")

# ============================================================================
# STEP 3: Update Teams Collection with Player IDs
# ============================================================================
print("\n[STEP 3] Updating teams collection with player_ids references...")
print("-" * 80)

for team in teams_collection.find({}):
    name = team.get("name")
    player_cursor = players_collection.find({"team": name})
    player_ids = [p["_id"] for p in player_cursor]
    teams_collection.update_one(
        {"_id": team["_id"]},
        {"$set": {"player_ids": player_ids}}
    )
    print(f"✅ Updated {name} with {len(player_ids)} player_ids")

# ============================================================================
# COMPLETE
# ============================================================================
print("\n" + "=" * 80)
print("MIGRATION COMPLETE!")
print("=" * 80)
print(f"Total players migrated: {len(player_docs)}")
print(f"Position ratings calculated: {scanned}")
print(f"Teams updated with player references")
print("\n✅ All player data successfully migrated and configured!")
print("=" * 80)
