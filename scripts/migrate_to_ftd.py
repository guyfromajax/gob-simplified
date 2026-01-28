#!/usr/bin/env python3
"""
Migrate Franchise Team Data to FTD Collection

This script extracts `franchise_teams` data from franchise documents and creates
separate `franchise_team_data` (FTD) documents for each team.

⚠️  WARNING: This is a one-time migration script. Run only once per database.

Usage:
    python3 scripts/migrate_to_ftd.py [--dry-run] [--database gob-staging]
"""

import os
import sys
import argparse
from datetime import datetime
from bson import ObjectId

# Add BackEnd to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables manually (for scripts)
def load_env_file(filepath):
    """Load environment variables from .env file manually."""
    env_vars = {}
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
    return env_vars

# Load environment variables
env_vars = {}
if os.path.exists(".env.local"):
    env_vars.update(load_env_file(".env.local"))
if os.path.exists(".env"):
    env_vars.update(load_env_file(".env"))

for key, value in env_vars.items():
    os.environ[key] = value

# Now import db module (it will use the env vars we just set)
try:
    from BackEnd.db import client, DB_NAME
except ImportError as e:
    print(f"❌ Failed to import BackEnd.db: {e}")
    print("   Make sure you're running from the project root directory")
    sys.exit(1)

if not client:
    print("❌ MongoDB client not available")
    print("   Check MONGO_URI in .env file")
    sys.exit(1)


def migrate_franchise_to_ftd(franchise_doc, db, dry_run=False):
    """
    Migrate a single franchise document's franchise_teams to FTD collection.
    
    Returns:
        tuple: (franchise_id, teams_migrated_count, errors)
    """
    franchise_id = franchise_doc.get("_id")
    franchise_teams = franchise_doc.get("franchise_teams", {})
    
    if not franchise_teams:
        return (franchise_id, 0, [])
    
    teams_migrated = 0
    errors = []
    franchise_team_data_collection = db["franchise_team_data"]
    
    for team_id_str, team_data in franchise_teams.items():
        try:
            # Convert team_id string to ObjectId if needed
            try:
                team_object_id = ObjectId(team_id_str)
            except:
                # If team_id_str is not a valid ObjectId, skip this team
                errors.append(f"Invalid team_id: {team_id_str}")
                continue
            
            # Extract team attributes (flatten from top-level keys)
            team_attributes = {
                "shot_threshold": team_data.get("shot_threshold", 90),
                "rebound_modifier": team_data.get("rebound_modifier", 1.0),
                "team_chemistry": team_data.get("team_chemistry", 8),
                "momentum_score": 0,  # Not stored in franchise_teams, default to 0
                "offensive_efficiency": team_data.get("offensive_efficiency", 0),
                "defensive_efficiency": team_data.get("defensive_efficiency", 0),
                "discipline": team_data.get("discipline", 0),
                "fight": team_data.get("fight", 0),
                "pt_opp_modifier": team_data.get("pt_opp_modifier", 0),
                "fb_opp_modifier": team_data.get("fb_opp_modifier", 0),
                "fb_efficiency": team_data.get("fb_efficiency", 0),
                "pt_efficiency": team_data.get("pt_efficiency", 0),
            }
            
            # Extract settings
            strategy_settings = team_data.get("strategy_settings", {})
            playbook_settings = team_data.get("playbook_settings", {})
            
            # Extract plays (remove game_stats, keep effectiveness/cloaking/momentum + season_stats)
            plays = {}
            for play_name, play_data in team_data.get("plays", {}).items():
                plays[play_name] = {
                    "play_id": play_data.get("play_id", ""),
                    "name": play_data.get("name", play_name),
                    "play_type": play_data.get("play_type", ""),
                    "play_focus": play_data.get("play_focus", ""),
                    "effectiveness": play_data.get("effectiveness", 0),
                    "cloaking": play_data.get("cloaking", 0),
                    "momentum": play_data.get("momentum", 0),
                    "season_stats": play_data.get("season_stats", {
                        "times_run": 0,
                        "successes": 0,
                        "player_points": {},
                        "effectiveness": 0.0
                    })
                    # NO game_stats - that stays in game docs only
                }
            
            # Extract scouting_data (defense + offense)
            scouting_data = {
                "defense": {},
                "offense": {}
            }
            
            # Process defense scouting
            defense_data = team_data.get("scouting_data", {}).get("defense", {})
            for defense_name, defense_stats in defense_data.items():
                if isinstance(defense_stats, dict):
                    scouting_data["defense"][defense_name] = {
                        "effectiveness": defense_stats.get("effectiveness", 0),
                        "momentum": defense_stats.get("momentum", 0),
                        "cloaking": defense_stats.get("cloaking", 0),
                        "season_stats": defense_stats.get("season_stats", {
                            "used": 0,
                            "success": 0,
                            "vs_motion": {"attempts": 0, "success": 0},
                            "vs_set": {"attempts": 0, "success": 0},
                            "vs_inside": {"attempts": 0, "success": 0},
                            "vs_attack": {"attempts": 0, "success": 0},
                            "vs_outside": {"attempts": 0, "success": 0},
                            "vs_motion_inside": {"attempts": 0, "success": 0},
                            "vs_motion_attack": {"attempts": 0, "success": 0},
                            "vs_motion_outside": {"attempts": 0, "success": 0},
                            "vs_set_inside": {"attempts": 0, "success": 0},
                            "vs_set_attack": {"attempts": 0, "success": 0},
                            "vs_set_outside": {"attempts": 0, "success": 0}
                        })
                        # NO game_stats - that stays in game docs only
                    }
            
            # Process offense scouting (if exists)
            offense_data = team_data.get("scouting_data", {}).get("offense", {})
            if offense_data:
                scouting_data["offense"] = offense_data.copy()
            
            # Extract training reports (if exists)
            training_reports = team_data.get("training_reports", {})
            latest_training = team_data.get("latest_training", None)
            
            # Create FTD document
            ftd_doc = {
                "franchise_id": franchise_id,
                "team_id": team_object_id,
                "team_attributes": team_attributes,
                "strategy_settings": strategy_settings,
                "playbook_settings": playbook_settings,
                "plays": plays,
                "scouting_data": scouting_data,
                "training_reports": training_reports,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            if latest_training:
                ftd_doc["latest_training"] = latest_training
            
            if not dry_run:
                # Insert or update FTD document
                franchise_team_data_collection.update_one(
                    {"franchise_id": franchise_id, "team_id": team_object_id},
                    {"$set": ftd_doc},
                    upsert=True
                )
            
            teams_migrated += 1
            
        except Exception as e:
            error_msg = f"Error migrating team {team_id_str}: {str(e)}"
            errors.append(error_msg)
            print(f"  ⚠️  {error_msg}")
            import traceback
            traceback.print_exc()
    
    return (franchise_id, teams_migrated, errors)


def main():
    parser = argparse.ArgumentParser(description="Migrate franchise_teams to FTD collection")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to database, just show what would be done")
    parser.add_argument("--database", default=None, help="Database name (default: from DB_NAME env or gob-staging)")
    args = parser.parse_args()
    
    # Determine database
    db_name = args.database or DB_NAME or "gob-staging"
    db = client[db_name]
    
    print(f"🔗 Connected to MongoDB")
    print(f"📊 Database: {db_name}")
    print(f"🔍 Mode: {'DRY RUN' if args.dry_run else 'LIVE MIGRATION'}")
    print()
    
    franchises_collection = db["franchises"]
    
    # Count franchises
    franchise_count = franchises_collection.count_documents({})
    print(f"📈 Found {franchise_count} franchise documents")
    print()
    
    if franchise_count == 0:
        print("✅ No franchises to migrate")
        return
    
    # Create index on franchise_team_data collection
    franchise_team_data_collection = db["franchise_team_data"]
    if not args.dry_run:
        print("📝 Creating index on franchise_team_data...")
        franchise_team_data_collection.create_index(
            [("franchise_id", 1), ("team_id", 1)],
            unique=True,
            name="franchise_team_unique"
        )
        print("✅ Index created")
        print()
    
    # Migrate each franchise
    total_teams_migrated = 0
    total_errors = []
    franchises_processed = 0
    
    print("🚀 Starting migration...")
    print()
    
    for franchise_doc in franchises_collection.find({}):
        franchise_id = franchise_doc.get("_id")
        franchises_processed += 1
        
        print(f"[{franchises_processed}/{franchise_count}] Migrating franchise {franchise_id}...")
        
        franchise_id_result, teams_count, errors = migrate_franchise_to_ftd(
            franchise_doc, db, dry_run=args.dry_run
        )
        
        total_teams_migrated += teams_count
        total_errors.extend(errors)
        
        if teams_count > 0:
            print(f"  ✅ Migrated {teams_count} teams")
        else:
            print(f"  ⚠️  No teams found to migrate")
        
        if errors:
            print(f"  ⚠️  {len(errors)} errors")
    
    print()
    print("=" * 60)
    print("📊 Migration Summary")
    print("=" * 60)
    print(f"Franchises processed: {franchises_processed}")
    print(f"Total teams migrated: {total_teams_migrated}")
    print(f"Total errors: {len(total_errors)}")
    
    if total_errors:
        print()
        print("⚠️  Errors encountered:")
        for error in total_errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(total_errors) > 10:
            print(f"  ... and {len(total_errors) - 10} more errors")
    
    if args.dry_run:
        print()
        print("🔍 DRY RUN MODE - No changes were made to the database")
        print("   Run without --dry-run to perform the actual migration")
    else:
        print()
        print("✅ Migration complete!")
        
        # Verify migration
        ftd_count = franchise_team_data_collection.count_documents({})
        print(f"📊 Total FTD documents created: {ftd_count}")


if __name__ == "__main__":
    main()
