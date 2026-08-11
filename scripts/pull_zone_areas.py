"""Read-only: pull Zone defenses from gob-staging and dump their zone areas.

Inspects the structure of `defenses` docs where defense_type == "Zone" so we can
map each zone defender to the spots/areas it covers (incl. triggered shifts) for
the Dynamic HCO Motion brief (Step 1 zone mismatch scoring).

Staging only. Read-only — no writes/deletes.
"""
import argparse
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=False)
    try:
        zones = list(connection.database.defenses.find({"defense_type": "Zone"}))
    finally:
        connection.close()
    print(f"Found {len(zones)} Zone defense docs in {args.db}.defenses\n")
    for doc in zones:
        name = doc.get("name") or doc.get("defense_name") or doc.get("_id")
        print("=" * 70)
        print(f"NAME: {name}")
        print(f"TOP-LEVEL KEYS: {sorted(doc.keys())}")
        doc.pop("_id", None)
        print(json.dumps(doc, indent=2, default=str)[:6000])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
