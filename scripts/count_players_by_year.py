#!/usr/bin/env python3
"""
Read-only: count players in gob.players by class `year`
(Senior / Junior / Sophomore / Freshman, plus any other/missing values).

Run from repo root:
  PYTHONPATH=. venv/bin/python scripts/count_players_by_year.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db_migration_cli import connect_migration_target

COLLECTION = "players"
CLASS_ORDER = ["Senior", "Junior", "Sophomore", "Freshman"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=False)
    coll = connection.database[COLLECTION]

    total = coll.count_documents({})
    counts = {
        doc["_id"]: doc["count"]
        for doc in coll.aggregate([{"$group": {"_id": "$year", "count": {"$sum": 1}}}])
    }

    print(f"[{args.db}.{COLLECTION}] total players: {total}\n")
    shown = 0
    for year in CLASS_ORDER:
        n = counts.pop(year, 0)
        shown += n
        print(f"  {year:<10} {n}")

    # Anything not in the canonical four (None / unexpected strings) — surfaced, not hidden.
    if counts:
        print("\n  Other / missing `year` values:")
        for key, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"    {str(key):<10} {n}")
            shown += n

    print(f"\n  accounted for: {shown} / {total}")
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
