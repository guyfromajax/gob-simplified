"""
Add mascot field to the universal teams collection in both gob and gob-staging.
Run from repo root: python3 scripts/add_mascots_to_teams.py
"""
import argparse
import sys
from pathlib import Path

# Project root and env loading (same pattern as migrate_to_ftd.py)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

# Mascot mapping (team name -> mascot)
MASCOTS = {
    "Morristown": "Pirates",
    "Bentley-Truman": "Sterling Knights",
    "Ocean City": "Admirals",
    "South Lancaster": "Bulldogs",
    "Xavien": "Elm Trees",
    "Little York": "Minutemen",
    "Lancaster": "Johnnies",
    "Four Corners": "Harvest",
}


def add_mascots_to_collection(teams_collection, db_label: str, *, apply: bool):
    """Add mascot field to teams in the given teams collection."""
    for team_name, mascot in MASCOTS.items():
        existing = teams_collection.find_one({"name": team_name}, {"mascot": 1})
        if not apply:
            print(f"  [{db_label}] would set mascot '{mascot}' for {team_name}" if existing else f"  [{db_label}] team '{team_name}' not found")
            continue
        result = teams_collection.update_one({"name": team_name}, {"$set": {"mascot": mascot}})
        if result.modified_count > 0:
            print(f"  [{db_label}] ✅ Set mascot '{mascot}' for {team_name}")
        elif result.matched_count > 0:
            print(f"  [{db_label}] ℹ️  {team_name} already has mascot")
        else:
            print(f"  [{db_label}] ⚠️  Team '{team_name}' not found")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=args.apply)
    add_mascots_to_collection(connection.database["teams"], args.db, apply=args.apply)
    connection.close()
    print("\n✅ Done.")


if __name__ == "__main__":
    main()
