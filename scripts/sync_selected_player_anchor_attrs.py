#!/usr/bin/env python3
"""
Sync anchor_* core attributes to match core attributes for a curated list of
universal players in gob.players and gob-staging.players.

Safety:
- Only updates the explicitly named players below.
- Matches by first_name, last_name, and team from teams/all_players_with_team_names.txt.
- Does not delete or replace any collections or documents.
"""

from __future__ import annotations

import os
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target
TXT_PATH = ROOT / "teams" / "all_players_with_team_names.txt"
TARGET_PLAYERS = (
    "Antoine Ellington",
    "Lucky Forte",
    "Porter DeGroot",
    "Siran Stanhope",
    "Ellis Clemons",
    "Booker Preston",
    "Jerry O'Neal",
    "JR Crawford",
    "Terry Axelford",
    "Sonny Carrozza",
    "Delmont Braggs",
)
ATTR_KEYS = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT")
IDX = {"first_name": 0, "last_name": 1, "team": 18}


def _parse_targets() -> dict[str, dict[str, str]]:
    lines = TXT_PATH.read_text().splitlines()
    rows: dict[str, dict[str, str]] = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) <= IDX["team"]:
            continue
        full_name = f"{parts[IDX['first_name']].strip()} {parts[IDX['last_name']].strip()}".strip()
        if full_name not in TARGET_PLAYERS:
            continue
        rows[full_name] = {
            "first_name": parts[IDX["first_name"]].strip(),
            "last_name": parts[IDX["last_name"]].strip(),
            "team": parts[IDX["team"]].strip(),
        }
    missing = [name for name in TARGET_PLAYERS if name not in rows]
    if missing:
        raise ValueError(f"Missing target players in source file: {missing}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", choices=("gob-staging", "gob"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    targets = _parse_targets()
    connection = connect_migration_target(args.db, write=args.apply)

    total_modified = 0
    coll = connection.database["players"]
    print(f"[info] {'Updating' if args.apply else 'Checking'} {args.db}.players anchor attrs")
    for full_name in TARGET_PLAYERS:
            row = targets[full_name]
            query = {
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "team": row["team"],
            }
            doc = coll.find_one(query, {"attributes": 1})
            if not doc:
                raise RuntimeError(f"{args.db}.players missing target player: {full_name} ({row['team']})")
            attrs = doc.get("attributes") or {}
            set_doc = {
                f"attributes.anchor_{key}": attrs.get(key, 0)
                for key in ATTR_KEYS
            }
            if args.apply:
                result = coll.update_one({"_id": doc["_id"]}, {"$set": set_doc})
                total_modified += result.modified_count
                print(f"  - {full_name} ({row['team']}): matched={result.matched_count} modified={result.modified_count}")
            else:
                print(f"  - {full_name} ({row['team']}): would sync {len(set_doc)} anchors")

    print(f"[done] Total modified documents: {total_modified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
