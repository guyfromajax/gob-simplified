"""
Add mascot field to the universal teams collection in both gob and gob-staging.
Run from repo root: python3 scripts/add_mascots_to_teams.py
"""
import os
import sys

# Project root and env loading (same pattern as migrate_to_ftd.py)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
sys.path.insert(0, _root)
os.chdir(_root)


def _load_env(filepath):
    out = {}
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip('"').strip("'")
    return out


for path in [".env.local", ".env"]:
    for k, v in _load_env(path).items():
        os.environ.setdefault(k, v)

from BackEnd.db import client

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


def add_mascots_to_collection(teams_collection, db_label: str):
    """Add mascot field to teams in the given teams collection."""
    for team_name, mascot in MASCOTS.items():
        result = teams_collection.update_one(
            {"name": team_name},
            {"$set": {"mascot": mascot}},
        )
        if result.modified_count > 0:
            print(f"  [{db_label}] ✅ Set mascot '{mascot}' for {team_name}")
        elif result.matched_count > 0:
            print(f"  [{db_label}] ℹ️  {team_name} already has mascot")
        else:
            print(f"  [{db_label}] ⚠️  Team '{team_name}' not found")


def main():
    if not client:
        print("❌ MongoDB client not available (MONGO_URI not set or connection failed).")
        return
    for db_name in ["gob", "gob-staging"]:
        print(f"\n📂 Database: {db_name}")
        teams = client[db_name]["teams"]
        add_mascots_to_collection(teams, db_name)
    print("\n✅ Done.")


if __name__ == "__main__":
    main()

