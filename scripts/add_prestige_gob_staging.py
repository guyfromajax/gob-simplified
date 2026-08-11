"""
Add prestige field (integer, 0) to all documents in the universal teams collection in gob-staging.
Run from repo root: python3 scripts/add_prestige_gob_staging.py
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

DB_NAME = "gob-staging"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target(DB_NAME, write=args.apply)
    teams = connection.database["teams"]
    matched = teams.count_documents({})
    modified = teams.update_many({}, {"$set": {"prestige": 0}}).modified_count if args.apply else 0
    print(f"[{DB_NAME}] {'Set' if args.apply else 'Would set'} prestige=0 on {modified if args.apply else matched} team(s)")
    connection.close()
    print("Done.")


if __name__ == "__main__":
    main()
