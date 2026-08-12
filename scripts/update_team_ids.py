import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

def update_team_ids(teams_collection, *, apply):
    for team in teams_collection.find():
        name = team["name"]
        team_id = name.upper().replace(" ", "_")

        if apply:
            teams_collection.update_one({"_id": team["_id"]}, {"$set": {"team_id": team_id}})
        print(f"✅ {'Updated' if apply else 'Would update'} team_id for {name} → {team_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=args.apply)
    update_team_ids(connection.database["teams"], apply=args.apply)
    connection.close()
