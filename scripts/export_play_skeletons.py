#!/usr/bin/env python3
"""
Export all play skeleton variants from the MongoDB `plays` collection.

Expected data shape per play (post-migration):
{
  "_id": ObjectId,
  "name": str,
  "play_type": str,
  "play_focus": str,
  "skeletons": {
    "successful": {...},
    "mid_play_change": {...},
    "contested": {...},
    "broken": {...}
  }
}

Outputs a JSON file (and also prints to stdout) containing all plays and their
four variants. With 7 plays × 4 variants, this yields 28 skeletons for analysis.
"""

import json
import argparse
from pathlib import Path
import sys
from typing import Any, Dict, List

from pymongo.collection import Collection

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target


def export_play_skeletons(plays_collection: Collection) -> List[Dict[str, Any]]:
    plays = list(plays_collection.find({}))
    exported = []
    for play in plays:
        exported.append(
            {
                "play_id": str(play.get("_id")),
                "name": play.get("name"),
                "play_type": play.get("play_type"),
                "play_focus": play.get("play_focus"),
                "skeletons": play.get("skeletons", {}),
            }
        )
    return exported


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--output", default="play_skeletons_export.json")
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=False)
    try:
        data = export_play_skeletons(connection.database["plays"])
    finally:
        connection.close()

    # Write to disk
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Also print to stdout for quick inspection
    json.dump(data, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
