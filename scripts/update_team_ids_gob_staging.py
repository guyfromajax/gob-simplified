"""
One-off: update team_id for four teams in gob-staging to match 128_teams.txt.
Run from repo root: python3 scripts/update_team_ids_gob_staging.py
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

DB_NAME = "gob-staging"

# name (exact match in DB) -> new team_id
UPDATES = [
    ("Queen's Guard", "queens_guard"),
    ("Couer d'Alene", "couer_d_alene"),
    ("Pike's Prep", "pikes_prep"),
    ("River's Edge", "rivers_edge"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target(DB_NAME, write=args.apply)
    teams = connection.database["teams"]
    for name, new_team_id in UPDATES:
        existing = teams.find_one({"name": name}, {"team_id": 1})
        result = teams.update_one({"name": name}, {"$set": {"team_id": new_team_id}}) if args.apply else None
        if existing and existing.get("team_id") != new_team_id:
            print(f"  {'Updated' if args.apply else 'Would update'} {name!r} -> team_id={new_team_id!r}")
        elif existing:
            print(f"  No change for {name!r} (already {new_team_id!r})")
        else:
            print(f"  ⚠ No team found with name={name!r}")
    print("Done.")
    connection.close()


if __name__ == "__main__":
    main()
