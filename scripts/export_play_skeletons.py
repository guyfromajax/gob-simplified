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
import os
import sys
from typing import Any, Dict, List

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection


def load_mongo_uri() -> str:
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    return mongo_uri


def get_plays_collection() -> Collection:
    mongo_uri = load_mongo_uri()
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client["gob"]
    return db["plays"]


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


def main(out_path: str = "play_skeletons_export.json") -> None:
    plays_collection = get_plays_collection()
    data = export_play_skeletons(plays_collection)

    # Write to disk
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Also print to stdout for quick inspection
    json.dump(data, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "play_skeletons_export.json"
    main(out_file)

