"""
One-off: Update IDA Academy -> IDA (name and team_id) in gob-staging teams collection.
Run from repo root: python3 scripts/fix_ida_team_gob_staging.py
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target("gob-staging", write=args.apply)
    teams = connection.database["teams"]
    existing = teams.find_one({"name": "IDA Academy"}, {"_id": 1})
    r = teams.update_one({"name": "IDA Academy"}, {"$set": {"name": "IDA", "team_id": "IDA"}}) if args.apply else None
    if existing:
        print(f"✅ [gob-staging] {'Updated' if args.apply else 'Would update'} team: IDA Academy → IDA")
    else:
        print("ℹ️  [gob-staging] No document with name 'IDA Academy' found (may already be IDA)")
    connection.close()
