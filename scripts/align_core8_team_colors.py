"""
Update primary/secondary colors for the core 8 teams in one explicit database.

Run from repo root:
  python3 scripts/align_core8_team_colors.py

Uses the shared explicit database boundary for both targets:
  - gob
  - gob-staging

If your staging DB is on a different cluster, run twice with different MONGO_URI.
"""
import os
import sys
import argparse
from pathlib import Path

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
sys.path.insert(0, _root)
from scripts.db_migration_cli import connect_migration_target

# Canonical core 8 (Conference 1): name -> (primary_color, secondary_color)
CORE_8_COLORS = {
    "Bentley-Truman": ("#4066b2", "#ffffff"),
    "Ocean City": ("#2a2168", "#00a89d"),
    "Lancaster": ("#d24a1b", "#000000"),
    "Four Corners": ("#c0976a", "#00954b"),
    "Morristown": ("#ec1d28", "#cccccc"),
    "Xavien": ("#016837", "#999999"),
    "Little York": ("#65308e", "#f6af38"),
    "South Lancaster": ("#7c2b24", "#e39649"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", choices=("gob-staging", "gob"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=args.apply)
    coll = connection.database.teams
    for name, (primary, secondary) in CORE_8_COLORS.items():
        count = coll.count_documents({"name": name})
        if args.apply:
            result = coll.update_many(
                    {"name": name},
                    {"$set": {"primary_color": primary, "secondary_color": secondary}},
                )
            print(f"  [{args.db}] {name}: matched={result.matched_count} modified={result.modified_count}")
        else:
            print(f"  [{args.db}] {name}: would update {count} document(s)")
    print("✅ Done.")


if __name__ == "__main__":
    main()
