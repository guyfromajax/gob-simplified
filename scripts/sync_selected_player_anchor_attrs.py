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
from pathlib import Path

from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
TXT_PATH = ROOT / "teams" / "all_players_with_team_names.txt"
TARGET_DBS = ("gob", "gob-staging")
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


def _load_env(filepath: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not filepath.exists():
        return values
    for raw_line in filepath.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_mongo_uri() -> str:
    for env_file in (ROOT / ".env.local", ROOT / ".env"):
        for key, value in _load_env(env_file).items():
            os.environ.setdefault(key, value)
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI not found in environment, .env.local, or .env")
    return uri


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
    uri = _load_mongo_uri()
    targets = _parse_targets()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)

    total_modified = 0
    for db_name in TARGET_DBS:
        coll = client[db_name]["players"]
        print(f"[info] Updating {db_name}.players anchor attrs")
        for full_name in TARGET_PLAYERS:
            row = targets[full_name]
            query = {
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "team": row["team"],
            }
            doc = coll.find_one(query, {"attributes": 1})
            if not doc:
                raise RuntimeError(f"{db_name}.players missing target player: {full_name} ({row['team']})")
            attrs = doc.get("attributes") or {}
            set_doc = {
                f"attributes.anchor_{key}": attrs.get(key, 0)
                for key in ATTR_KEYS
            }
            result = coll.update_one({"_id": doc["_id"]}, {"$set": set_doc})
            total_modified += result.modified_count
            print(f"  - {full_name} ({row['team']}): matched={result.matched_count} modified={result.modified_count}")

    print(f"[done] Total modified documents across both DBs: {total_modified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
