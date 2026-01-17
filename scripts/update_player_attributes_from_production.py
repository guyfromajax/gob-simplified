# scripts/update_player_attributes_from_production.py
"""
Update player attributes (anchor and regular) in the gob database from production JSON files.

This script updates:
- South Lancaster players from south_lancaster_production.json
- Four Corners players from four_corners_production.json

Only updates attributes and anchor_attributes, nothing else.
"""
import os
import sys
import json
from pathlib import Path

# Make BackEnd importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from BackEnd.db import players_collection, DB_NAME
from BackEnd.constants import ALL_ATTRS

# Ensure we're using the gob database (not staging)
if "staging" in DB_NAME.lower():
    raise SystemExit(f"❌ ERROR: Script is configured for 'gob' database, but DB_NAME is '{DB_NAME}'. "
                     f"Please set MONGO_DB_NAME environment variable to 'gob' or update your connection.")

print(f"📊 Using database: {DB_NAME}")
print(f"🔍 Searching for players in the '{DB_NAME}' database...\n")

TEAMS_DIR = Path(__file__).resolve().parent.parent / "teams"

# Attribute keys to update (all regular attributes + NG)
ATTRIBUTE_KEYS = ALL_ATTRS + ["NG"]  # SC, SH, ID, OD, PS, BH, RB, ST, AG, FT, ND, IQ, CH, EM, MO, NG

def update_team_players(team_name: str, json_file: Path):
    """Update all players for a team from the JSON file."""
    print(f"\n{'='*80}")
    print(f"📁 Processing: {json_file.name}")
    print(f"🏀 Team: {team_name}")
    print(f"{'='*80}\n")
    
    if not json_file.exists():
        print(f"❌ File not found: {json_file}")
        return 0, 0, 0
    
    data = json.loads(json_file.read_text(encoding="utf-8"))
    players_json = data.get("players", [])
    
    if not players_json:
        print(f"⚠️  No players found in {json_file.name}")
        return 0, 0, 0
    
    matched_count = 0
    updated_count = 0
    missed_count = 0
    
    for p_json in players_json:
        first_name = p_json.get("first_name", "").strip()
        last_name = p_json.get("last_name", "").strip()
        jersey = p_json.get("jersey")
        
        if not first_name or not last_name:
            print(f"⚠️  Skipping player with missing name: {p_json}")
            continue
        
        # Find player in database by team, first_name, last_name, and jersey
        # Try multiple matching strategies for robustness
        filt = {
            "team": team_name,
            "first_name": first_name,
            "last_name": last_name
        }
        
        if jersey is not None:
            filt["jersey"] = jersey
        
        db_player = players_collection.find_one(filt)
        
        # If not found with jersey, try without jersey
        if not db_player and jersey is not None:
            filt_no_jersey = {
                "team": team_name,
                "first_name": first_name,
                "last_name": last_name
            }
            db_player = players_collection.find_one(filt_no_jersey)
        
        if not db_player:
            missed_count += 1
            print(f"❌ MISS: {team_name} — {first_name} {last_name} (jersey {jersey})")
            continue
        
        matched_count += 1
        
        # Build attribute updates
        # Get current attributes from database (if they exist)
        current_attrs = db_player.get("attributes", {})
        
        # Build update dictionary for attributes
        update_fields = {}
        
        # Update regular attributes
        for attr_key in ATTRIBUTE_KEYS:
            new_value = p_json.get(attr_key)
            if new_value is not None:
                attr_path = f"attributes.{attr_key}"
                current_value = current_attrs.get(attr_key)
                update_fields[attr_path] = new_value
                
                # Also update anchor_ attribute (set to same value as regular attribute)
                anchor_key = f"anchor_{attr_key}"
                # Only update anchor for attributes that should have anchors (not NG, CH, EM, MO)
                if attr_key not in ["NG", "CH", "EM", "MO"]:
                    anchor_path = f"attributes.{anchor_key}"
                    current_anchor_value = current_attrs.get(anchor_key)
                    update_fields[anchor_path] = new_value
        
        if not update_fields:
            print(f"⚠️  No attributes to update for {first_name} {last_name}")
            continue
        
        # Perform the update
        result = players_collection.update_one(
            {"_id": db_player["_id"]},
            {"$set": update_fields}
        )
        
        if result.modified_count > 0:
            updated_count += 1
            # Show what changed
            changed_attrs = []
            for attr_key in ATTRIBUTE_KEYS:
                new_val = p_json.get(attr_key)
                if new_val is not None:
                    old_val = current_attrs.get(attr_key, "N/A")
                    if old_val != new_val:
                        changed_attrs.append(f"{attr_key}:{old_val}→{new_val}")
            
            change_summary = ", ".join(changed_attrs[:5])  # Show first 5 changes
            if len(changed_attrs) > 5:
                change_summary += f" (+{len(changed_attrs)-5} more)"
            
            print(f"✅ UPDATED: {team_name} — {first_name} {last_name} (jersey {jersey})")
            if changed_attrs:
                print(f"   Changes: {change_summary}")
        else:
            print(f"✓ OK: {team_name} — {first_name} {last_name} (jersey {jersey}) - no changes needed")
    
    return matched_count, updated_count, missed_count

# Process both teams
total_matched = total_updated = total_missed = 0

# South Lancaster
sl_file = TEAMS_DIR / "south_lancaster_production.json"
sl_matched, sl_updated, sl_missed = update_team_players("South Lancaster", sl_file)
total_matched += sl_matched
total_updated += sl_updated
total_missed += sl_missed

# Four Corners
fc_file = TEAMS_DIR / "four_corners_production.json"
fc_matched, fc_updated, fc_missed = update_team_players("Four Corners", fc_file)
total_matched += fc_matched
total_updated += fc_updated
total_missed += fc_missed

# Summary
print(f"\n{'='*80}")
print("📊 SUMMARY")
print(f"{'='*80}")
print(f"Database: {DB_NAME}")
print(f"Players matched: {total_matched}")
print(f"Players updated: {total_updated}")
print(f"Players not found: {total_missed}")
print(f"\nExpected: 24 players (12 per team)")
if total_matched == 24:
    print("✅ All 24 players found and processed!")
elif total_matched < 24:
    print(f"⚠️  Only found {total_matched}/24 players. Check for missing players above.")
print(f"{'='*80}\n")

